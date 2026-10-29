#include "NativeMovieProtocol.h"
#include <iostream>
#include <stdexcept>
using namespace mct;
static void require(bool ok, const char* reason) { if (!ok) throw std::runtime_error(reason); }
static Json control(const Json& view, const char* id) {
    for (const auto& row : view.at("controls")) if (row.at("id") == id) return row;
    throw std::runtime_error("Expected match control missing");
}
static std::string command(const Json& view, const char* id) {
    return Json{{"protocol", 1}, {"session", view.at("session")}, {"surface", view.at("surface")},
        {"generation", view.at("generation")}, {"revision", control(view, id).at("revision")}, {"control", id}}.dump();
}
static std::string ready(const Json& view) {
    return Json{{"protocol", 1}, {"session", view.at("session")}, {"surface", view.at("surface")},
        {"generation", view.at("generation")}, {"event", "ready"}}.dump();
}
static bool hasControl(const Json& view, const char* id) {
    for (const auto& row : view.at("controls")) if (row.at("id") == id) return true;
    return false;
}
static void returnAbandonmentBindingChecks() {
    CareerLayoutScope scope{true, true, true, false, "test-owned-return-scope", 1,
                            NativeMenuSurface::Pause};
    Json training = {{"protocol", 1}, {"offline", true}, {"bridge_session", scope.nonce},
        {"session", {{"id", "training-activity"}, {"fixture_id", ""}, {"kind", "training"},
            {"state", "training"}, {"worker_running", true}, {"busy", false}}},
        {"career", {{"pending_session", {{"session_id", "saved-career-activity"},
            {"fixture_id", "saved-career-fixture"}}}}},
        {"telemetry", {{"lesson_id", "power-shots"}}}};
    const auto directReturn = [&](const Json& state, const char* reason) {
        NativeMovieProtocol host;
        require(host.open(scope, state), "Training Return scope did not open");
        const auto view = host.publish(scope, state, 100);
        require(!hasControl(view, "match.confirm_return") &&
            control(view, "pause.return")["return_commit"] == true, reason);
        require(host.readyMessage(ready(view), scope), "Training Return view did not become ready");
        const auto effect = host.select(command(view, "pause.return"), scope, state, true);
        require(effect.accepted && effect.action == "return_hub" &&
            effect.payload["expected_session_id"] == stringValue(objectValue(state, "session"), "id") &&
            effect.payload["expected_fixture_id"] == stringValue(objectValue(state, "session"), "fixture_id") &&
            effect.payload["abandon"] == false, reason);
    };
    directReturn(training, "Unrelated pending Career forced training Return confirmation");

    auto trainingIdentityCollision = training;
    trainingIdentityCollision["session"]["id"] = "saved-career-activity";
    trainingIdentityCollision["session"]["fixture_id"] = "saved-career-fixture";
    directReturn(trainingIdentityCollision, "Training activity identity collision was treated as Career");

    auto careerWrongFixture = training;
    careerWrongFixture["session"]["kind"] = "career";
    careerWrongFixture["session"]["id"] = "saved-career-activity";
    careerWrongFixture["session"]["fixture_id"] = "another-career-fixture";
    careerWrongFixture["session"]["state"] = "Playing";
    directReturn(careerWrongFixture, "Mismatched Career fixture triggered abandon confirmation");

    auto careerWrongSession = training;
    careerWrongSession["session"]["kind"] = "career";
    careerWrongSession["session"]["id"] = "another-career-activity";
    careerWrongSession["session"]["fixture_id"] = "saved-career-fixture";
    careerWrongSession["session"]["state"] = "Playing";
    directReturn(careerWrongSession, "Mismatched Career session triggered abandon confirmation");
}
static void forfeitChecks() {
    CareerLayoutScope scope{true, true, true, false, "test-owned-forfeit-session", 1, NativeMenuSurface::Pause};
    scope.matchInProgress = true;
    Json state = {{"protocol", 1}, {"offline", true}, {"bridge_session", scope.nonce},
        {"session", {{"id", "forfeit-activity"}, {"fixture_id", "career-1:s1:league:1:0"}, {"kind", "career"},
            {"state", "Playing"}, {"worker_running", true}, {"busy", false}}},
        {"career", {{"pending_session", {{"fixture_id", "career-1:s1:league:1:0"},
            {"session_id", "forfeit-activity"}}}}}};
    NativeMovieProtocol host;
    require(host.open(scope, state), "Forfeit pause did not open");
    auto view = host.publish(scope, state, 100);
    require(control(view, "pause.forfeit")["enabled"] == true &&
        control(view, "pause.forfeit")["return_commit"] == false, "Forfeit entry committed without confirmation");
    require(NativeCareerLayout::supportedAction("forfeit_match"), "Forfeit dispatch not supported");
    auto effect = host.select(command(view, "pause.forfeit"), scope, state, true);
    require(effect.accepted && effect.kind == CareerLayoutEffectKind::Navigate && effect.action.empty() &&
        !effect.payload.contains("confirm") && effect.payload.size() == 2,
        "Opening Forfeit confirmation dispatched or preconfirmed a result");
    auto confirm = host.publish(scope, state, 101);
    require(control(confirm, "match.confirm_forfeit")["return_commit"] == true &&
        control(confirm, "match.cancel_forfeit")["return_commit"] == false && confirm["return_pending"] == false,
        "Forfeit confirmation hold markers are incorrect");
    const auto reconfirm = [&]() {
        require(host.open(scope, state), "Forfeit confirmation reset failed");
        auto entry = host.publish(scope, state, 101);
        require(host.select(command(entry, "pause.forfeit"), scope, state, true).accepted,
            "Forfeit entry reset refused");
        return host.publish(scope, state, 101);
    };
    auto changed = state; changed["session"]["id"] = "another-activity";
    require(!host.select(command(confirm, "match.confirm_forfeit"), scope, changed, true).accepted,
        "Stale Forfeit confirmation accepted another activity");
    confirm = reconfirm();
    changed = state; changed["career"]["pending_session"]["fixture_id"] = "other-fixture";
    require(!host.select(command(confirm, "match.confirm_forfeit"), scope, changed, true).accepted,
        "Forfeit accepted a mismatched pending fixture");
    confirm = reconfirm();
    changed = state; changed["session"]["busy"] = true;
    require(!host.select(command(confirm, "match.confirm_forfeit"), scope, changed, true).accepted,
        "Busy Forfeit confirmation dispatched");
    confirm = reconfirm();
    changed = state; changed["session"]["state"] = "Career Ready";
    require(!host.select(command(confirm, "match.confirm_forfeit"), scope, changed, true).accepted,
        "Finished career state accepted Forfeit");
    confirm = reconfirm();
    auto ended = scope; ended.matchInProgress = false;
    require(!host.select(command(confirm, "match.confirm_forfeit"), ended, state, true).accepted,
        "Ended native match accepted Forfeit before publication caught up");
    confirm = reconfirm();
    require(!host.select(command(confirm, "match.confirm_forfeit"), scope, state, false).accepted,
        "Unconsumed native callback accepted Forfeit");
    for (int lost = 0; lost < 4; ++lost) {
        confirm = reconfirm();
        changed = state;
        auto live = scope;
        if (lost == 0) changed["session"]["worker_running"] = false;
        if (lost == 1) changed["session"]["state"] = "Career Ready";
        if (lost == 2) changed["session"]["id"] = "another-activity";
        if (lost == 3) live.matchInProgress = false;
        auto lostView = host.publish(live, changed, 101);
        require(!hasControl(lostView, "match.confirm_forfeit"), "Lost activity retained Forfeit confirmation");
        auto restored = host.publish(scope, state, 101);
        require(!hasControl(restored, "match.confirm_forfeit") && hasControl(restored, "pause.forfeit"),
            "Restored snapshot resurrected Forfeit confirmation without a new entry click");
    }
    confirm = reconfirm();
    effect = host.select(command(confirm, "match.cancel_forfeit"), scope, state, true);
    require(effect.accepted && effect.kind == CareerLayoutEffectKind::Navigate && effect.action.empty(),
        "Back from Forfeit dispatched a result");
    view = host.publish(scope, state, 102);
    require(hasControl(view, "pause.resume") && !hasControl(view, "match.confirm_forfeit"),
        "Back did not restore ordinary pause");
    require(!host.select(command(confirm, "match.confirm_forfeit"), scope, state, true).accepted,
        "Cancelled Forfeit confirmation remained usable");
    require(host.select(command(view, "pause.forfeit"), scope, state, true).accepted, "Forfeit reopen refused");
    confirm = host.publish(scope, state, 103);
    effect = host.select(command(confirm, "match.confirm_forfeit"), scope, state, true);
    const Json expected = {{"expected_session_id", "forfeit-activity"},
        {"expected_fixture_id", "career-1:s1:league:1:0"}, {"confirm", true}};
    require(effect.accepted && effect.action == "forfeit_match" && effect.payload == expected &&
        effect.originalConsumptionRequired && effect.originalConsumptionSatisfied,
        "Forfeit dispatch did not preserve exact confirmed identity");
    require(!host.select(command(confirm, "match.confirm_forfeit"), scope, state, true).accepted,
        "Forfeit confirmation replay accepted twice");
    require(host.open(scope, state), "Forfeit scope reopen failed");
    view = host.publish(scope, state, 104);
    auto noMatch = host.publish(ended, state, 105);
    require(!hasControl(noMatch, "pause.forfeit") && noMatch["generation"] != view["generation"],
        "Native ended observation did not invalidate Forfeit view");
    auto pending = host.publish(scope, state, 106, {}, {}, true);
    require(!hasControl(pending, "pause.forfeit") && !hasControl(pending, "match.confirm_forfeit"),
        "Pending Return still offered Forfeit");
    for (const auto& kind : {"training", "calibration"}) {
        changed = state; changed["session"]["kind"] = kind;
        require(host.open(scope, changed), "Non-career pause did not open");
        require(!hasControl(host.publish(scope, changed, 107), "pause.forfeit"), "Non-career activity offered Forfeit");
    }
    changed = state; changed["session"]["worker_running"] = false;
    require(host.open(scope, changed), "Workerless pause did not open");
    require(!hasControl(host.publish(scope, changed, 108), "pause.forfeit"), "Workerless activity offered Forfeit");
    changed = state; changed["session"]["busy"] = true;
    require(host.open(scope, changed), "Busy pause did not open");
    require(control(host.publish(scope, changed, 109), "pause.forfeit")["enabled"] == false,
        "Busy activity enabled Forfeit entry");
    auto results = scope; results.surface = NativeMenuSurface::Results; ++results.generation;
    require(host.open(results, state), "Forfeit results scope did not open");
    require(!hasControl(host.publish(results, state, 110), "pause.forfeit"), "Results offered Forfeit");
    for (int unsafe = 0; unsafe < 4; ++unsafe) {
        auto rejected = scope;
        if (unsafe == 0) rejected.online = true;
        if (unsafe == 1) rejected.owned = false;
        if (unsafe == 2) rejected.offline = false;
        if (unsafe == 3) rejected.fresh = false;
        require(!host.open(rejected, state), "Unsafe game scope opened Forfeit controls");
    }
}
static void forfeitResultLabels() {
    CareerLayoutScope scope{true, true, true, false, "test-owned-forfeit-results", 1, NativeMenuSurface::Results};
    for (int scenario = 0; scenario < 3; ++scenario) {
        const bool awayHuman = scenario == 2;
        Json result = {{"session_id", "saved-forfeit"}, {"fixture_id", "career-1:s1:league:1:0"},
            {"home", awayHuman ? "aurora" : "human"}, {"away", awayHuman ? "human" : "aurora"},
            {"home_score", scenario == 0 ? 0 : awayHuman ? 2 : 7},
            {"away_score", scenario == 0 ? 0 : awayHuman ? 7 : 2}, {"winner", "aurora"},
            {"provenance", "forfeit"}, {"outcome", "forfeited"}, {"forfeited_by", "human"}, {"simulated", false}};
        Json state = {{"protocol", 1}, {"offline", true}, {"bridge_session", scope.nonce},
            {"session", {{"id", "saved-forfeit"}, {"fixture_id", "career-1:s1:league:1:0"},
                {"kind", "career"}, {"state", "Career Ready"}, {"worker_running", false}, {"busy", false}}},
            {"career", {{"pending_session", nullptr}}}, {"latest_result", result}};
        NativeMovieProtocol host;
        require(host.open(scope, state), "Saved Forfeit results did not open");
        auto view = host.publish(scope, state, 100);
        require(view["body"].get<std::string>().find(u8"FORFEIT \u2014 LOSS saved") != std::string::npos &&
            view["body"].get<std::string>().find("score at forfeit") != std::string::npos &&
            control(view, "results.return")["enabled"] == true, "Saved results did not identify forfeited loss");
        state["latest_result"]["winner"] = "human";
        auto malformed = host.publish(scope, state, 101);
        require(malformed["body"].get<std::string>().find("FORFEIT") == std::string::npos,
            "Malformed Forfeit result claimed an authoritative loss");
        state["latest_result"] = {{"session_id", "saved-forfeit"}, {"fixture_id", "career-1:s1:league:1:0"},
            {"home", "human"}, {"away", "aurora"}, {"home_score", 7}, {"away_score", 2},
            {"winner", "human"}, {"provenance", "game"}, {"simulated", false}};
        auto played = host.publish(scope, state, 102);
        require(played["body"].get<std::string>().find("Your result is saved.") != std::string::npos &&
            played["body"].get<std::string>().find("FORFEIT") == std::string::npos,
            "Normal saved result label changed");
    }
}
static Json continuationState(const std::string& nonce) {
    Json recruits = Json::object();
    const char* specs[][2] = {{"anchor", "keeper"}, {"shield", "defender"}, {"relay", "passer"},
        {"comet", "attacker"}, {"orbit", "all-rounder"}};
    for (const auto& spec : specs)
        recruits[spec[0]] = {{"id", spec[0]}, {"role", spec[1]}, {"name", std::string("Bot ") + spec[0]}, {"level", 2}};
    Json fixtures = Json::array();
    fixtures.push_back({{"id", "career-1:s1:league:1:0"}, {"home", "human"}, {"away", "aurora"}, {"round", 1},
        {"status", "completed"}, {"result", {{"home_score", 3}, {"away_score", 1}, {"winner", "human"},
            {"provenance", "game"}, {"simulated", false}}}});
    fixtures.push_back({{"id", "career-1:s1:league:1:1"}, {"home", "aurora"}, {"away", "cinder"}, {"round", 1},
        {"status", "scheduled"}});
    for (int round = 2; round <= 8; ++round)
        fixtures.push_back({{"id", "career-1:s1:league:" + std::to_string(round) + ":0"},
            {"home", round % 2 ? "human" : "cinder"}, {"away", round % 2 ? "tidal" : "human"},
            {"round", round}, {"status", "scheduled"}});
    Json season = {{"clubs", Json::array()}, {"fixtures", fixtures}};
    Json career = {{"id", "career-1"}, {"team_name", "Test Club"}, {"format", 3},
        {"squad", Json::array({"anchor", "shield", "relay", "comet"})}, {"lineup", Json::array({"shield", "relay"})},
        {"recruits", recruits}, {"pending_session", nullptr}, {"current_season", 0},
        {"seasons", Json::array({season})}};
    return {{"protocol", 1}, {"offline", true}, {"bridge_session", nonce},
        {"session", {{"id", "finished-session"}, {"fixture_id", "career-1:s1:league:1:0"}, {"kind", "career"},
            {"state", "Career Ready"}, {"worker_running", false}, {"busy", false}}},
        {"career", career},
        {"latest_result", {{"session_id", "finished-session"}, {"fixture_id", "career-1:s1:league:1:0"},
            {"home", "human"}, {"away", "aurora"}, {"home_score", 3}, {"away_score", 1}, {"winner", "human"},
            {"provenance", "game"}, {"simulated", false}}},
        {"next_fixture", {{"id", "career-1:s1:league:2:0"}, {"home", "cinder"}, {"away", "human"}, {"round", 2},
            {"status", "scheduled"}}}};
}
static std::vector<std::string> ids(const Json& view) {
    std::vector<std::string> out;
    for (const auto& row : view.at("controls")) out.push_back(row.at("id").get<std::string>());
    return out;
}
static bool contains(const Json& view, const char* text) {
    return view.at("body").get<std::string>().find(text) != std::string::npos;
}
static void continuationChecks() {
    CareerLayoutScope scope{true, true, true, false, "test-owned-results-continuation", 1, NativeMenuSurface::Results};
    auto state = continuationState(scope.nonce);
    NativeMovieProtocol host;
    require(host.open(scope, state), "Continuation results did not open");
    double now = 200;
    auto root = host.publish(scope, state, now);
    const std::vector<std::string> rootIds = {"results.next", "results.schedule", "results.preset",
        "results.settings", "results.return"};
    require(ids(root) == rootIds, "Results root is not exactly the five ordered controls");
    const char* labels[] = {"Play Next Match", "Schedule", "Change Preset", "Settings", "Exit"};
    for (std::size_t index = 0; index < rootIds.size(); ++index)
        require(root["controls"][index]["label"] == labels[index] && root["controls"][index]["enabled"] == true,
            "Results root label or enabled state changed");
    require(control(root, "results.preset")["stock"] == "preset" &&
        control(root, "results.settings")["stock"] == "settings" &&
        control(root, "results.return")["return_commit"] == true &&
        control(root, "results.next")["return_commit"] == true &&
        control(root, "results.schedule")["return_commit"] == false, "Root routes or commit hints changed");
    require(contains(root, "Your result is saved.") && contains(root, "Next match: Round 2"), "Root body lost next match");
    auto preset = host.select(command(root, "results.preset"), scope, state, true);
    require(preset.accepted && preset.kind == CareerLayoutEffectKind::PreserveStockRoute &&
        preset.stock == StockRoute::Preset && preset.action.empty(), "Change Preset route changed");
    root = host.publish(scope, state, ++now);
    auto settings = host.select(command(root, "results.settings"), scope, state, true);
    require(settings.accepted && settings.stock == StockRoute::Settings && settings.action.empty(),
        "Settings route changed");
    root = host.publish(scope, state, ++now);
    auto exit = host.select(command(root, "results.return"), scope, state, true);
    require(exit.accepted && exit.action == "return_hub" && exit.payload["abandon"] == false &&
        exit.payload["expected_session_id"] == "finished-session", "Exit did not use exact return_hub");

    // Schedule is local, paged and read-only.
    require(host.open(scope, state), "Results reopen failed");
    root = host.publish(scope, state, ++now);
    auto effect = host.select(command(root, "results.schedule"), scope, state, true);
    require(effect.accepted && effect.kind == CareerLayoutEffectKind::Navigate && effect.action.empty(),
        "Schedule dispatched");
    auto schedule = host.publish(scope, state, ++now);
    require(schedule["title"] == "Schedule" && contains(schedule, "Page 1 of 2") &&
        contains(schedule, "Round 1 result: Test Club 3, Aurora Athletic 1") && contains(schedule, " - next") &&
        !contains(schedule, "Aurora Athletic vs Cinder"), "Schedule content is wrong");
    require(ids(schedule) == std::vector<std::string>{"results.schedule_prev", "results.schedule_next",
        "results.schedule_back"} && control(schedule, "results.schedule_prev")["enabled"] == false,
        "Schedule paging controls are wrong");
    effect = host.select(command(schedule, "results.schedule_next"), scope, state, true);
    require(effect.accepted && effect.kind == CareerLayoutEffectKind::Navigate && effect.action.empty(), "Paging dispatched");
    auto second = host.publish(scope, state, ++now);
    require(contains(second, "Page 2 of 2") && control(second, "results.schedule_next")["enabled"] == false &&
        control(second, "results.schedule_prev")["enabled"] == true, "Schedule did not page");
    require(!host.select(command(schedule, "results.schedule_next"), scope, state, true).accepted,
        "Old schedule page accepted");
    effect = host.select(command(second, "results.schedule_back"), scope, state, true);
    require(effect.accepted && effect.kind == CareerLayoutEffectKind::Navigate && effect.action.empty(),
        "Schedule Back dispatched");
    root = host.publish(scope, state, ++now);
    require(ids(root) == rootIds, "Schedule Back did not restore the root");
    require(host.select(command(root, "results.schedule"), scope, state, true).accepted, "Schedule reopen refused");
    auto changed = state; changed["session"]["id"] = "another-session";
    require(!hasControl(host.publish(scope, changed, ++now), "results.schedule_back"),
        "Schedule survived a changed activity");
    require(ids(host.publish(scope, state, ++now)) == rootIds, "Schedule resurrected without a new click");

    // One activation dispatches the saved lineup; there is no preview or second Start.
    root = host.publish(scope, state, ++now);
    require(!host.select(command(root, "results.next"), scope, state, false).accepted,
        "Unconsumed direct continuation dispatched");
    changed = state; changed["next_fixture"]["id"] = "career-1:s1:league:3:0";
    require(!host.select(command(root, "results.next"), scope, changed, true).accepted,
        "Direct continuation accepted a changed next fixture");
    changed = state; changed["career"]["lineup"] = Json::array({"relay", "comet"});
    require(!host.select(command(root, "results.next"), scope, changed, true).accepted,
        "Direct continuation accepted a changed saved lineup");
    changed = state; changed["session"]["id"] = "finished-session-2";
    require(!host.select(command(root, "results.next"), scope, changed, true).accepted,
        "Direct continuation accepted a changed activity");
    effect = host.select(command(root, "results.next"), scope, state, true);
    const Json expected = {{"expected_session_id", "finished-session"},
        {"expected_fixture_id", "career-1:s1:league:1:0"}, {"expected_next_fixture_id", "career-1:s1:league:2:0"},
        {"lineup_ids", Json::array({"shield", "relay"})}};
    require(effect.accepted && effect.kind == CareerLayoutEffectKind::Dispatch &&
        effect.action == "prepare_next_match" && effect.payload == expected &&
        !effect.payload.contains("continuation_intent") && effect.originalConsumptionRequired,
        "Play Next Match did not directly dispatch the exact saved lineup");
    require(!host.select(command(root, "results.next"), scope, state, true).accepted,
        "Direct continuation replay accepted");
    require(ids(host.publish(scope, state, ++now)) == rootIds,
        "Direct continuation opened an extra menu");
    auto pending = host.publish(scope, state, ++now, {}, {}, true);
    require(!hasControl(pending, "results.next"), "Pending Return offered continuation");
    auto otherNonce = scope; otherNonce.nonce = "test-owned-results-other-nonce";
    auto foreign = state; foreign["bridge_session"] = otherNonce.nonce;
    require(host.publish(otherNonce, foreign, ++now)["active"] == false, "Other nonce published results");

    // No next fixture, unsaved result and all saved lineup sizes.
    auto finale = state; finale["next_fixture"] = nullptr;
    require(host.open(scope, finale), "Finale results did not open");
    auto ended = host.publish(scope, finale, ++now);
    require(ids(ended) == rootIds && control(ended, "results.next")["enabled"] == false &&
        control(ended, "results.next")["reason"].get<std::string>().find("season is complete") != std::string::npos &&
        contains(ended, "no next match") && control(ended, "results.return")["enabled"] == true &&
        control(ended, "results.schedule")["enabled"] == true, "No-next state did not explain disabled continuation");
    require(!host.select(command(ended, "results.next"), scope, finale, true).accepted, "Disabled continuation accepted");
    auto unsaved = state; unsaved["latest_result"]["fixture_id"] = "other-fixture"; unsaved["error"] = "Save unavailable";
    require(host.open(scope, unsaved), "Unsaved results did not open");
    auto failed = host.publish(scope, unsaved, ++now);
    require(ids(failed) == std::vector<std::string>{"results.retry_save", "results.next", "results.schedule",
        "results.preset", "results.settings", "results.return"}, "Unsaved recovery controls are wrong");
    require(control(failed, "results.retry_save")["enabled"] == true && control(failed, "results.next")["enabled"] == false &&
        control(failed, "results.return")["enabled"] == false, "Unsaved result allowed continuation or exit");
    for (int format = 1; format <= 4; ++format) {
        auto sized = state;
        const std::vector<std::string> squad = {"anchor", "shield", "relay", "comet"};
        const std::vector<std::string> lineup(squad.begin(), squad.begin() + format - 1);
        sized["career"]["format"] = format;
        sized["career"]["lineup"] = lineup;
        require(host.open(scope, sized), "Sized results did not open");
        root = host.publish(scope, sized, ++now);
        require(ids(root) == rootIds, "Sized results introduced an extra page");
        effect = host.select(command(root, "results.next"), scope, sized, true);
        require(effect.accepted && effect.action == "prepare_next_match" &&
            effect.payload["lineup_ids"] == Json(lineup) && effect.payload.size() == 4,
            "Direct continuation changed the saved lineup");
    }
    auto invalid = state; invalid["career"]["lineup"] = Json::array({"shield", "shield"});
    require(host.open(scope, invalid), "Invalid-roster results did not open");
    root = host.publish(scope, invalid, ++now);
    require(control(root, "results.next")["enabled"] == false &&
        !host.select(command(root, "results.next"), scope, invalid, true).accepted,
        "Invalid saved lineup allowed direct continuation");

    // Pending results recovery offers the game's Settings, never the old Options submenu.
    require(host.open(scope, state), "Pending results did not open");
    auto held = host.publish(scope, state, ++now, {}, {}, true);
    require(!hasControl(held, "results.options") && control(held, "results.settings")["label"] == "Settings" &&
        control(held, "results.settings")["stock"] == "settings" && control(held, "results.settings")["enabled"] == false,
        "Held results recovery did not use a disabled Settings route");
    auto released = host.publish(scope, state, ++now, {}, {}, true, Json::object(), false, false);
    require(control(released, "results.settings")["enabled"] == true, "Released results recovery kept Settings disabled");
}
int main() {
    try {
        returnAbandonmentBindingChecks();
        forfeitChecks();
        forfeitResultLabels();
        continuationChecks();
        CareerLayoutScope scope{true, true, true, false, "test-owned-native-session", 1, NativeMenuSurface::Pause};
        Json state = {{"protocol", 1}, {"offline", true}, {"bridge_session", scope.nonce},
            {"session", {{"id", "activity-1"}, {"fixture_id", "career-1:s1:league:1:0"}, {"kind", "career"},
                {"state", "Playing"}, {"worker_running", true}, {"busy", false}}},
            {"career", {{"pending_session", {{"fixture_id", "career-1:s1:league:1:0"}, {"session_id", "activity-1"}}}}}};
        NativeMovieProtocol host;
        require(host.open(scope, state), "Pause did not open");
        auto view = host.publish(scope, state, 100);
        require(view["return_pending"] == false && view["return_hold"] == false &&
            control(view, "pause.return")["return_commit"] == false, "Unfinished confirmation held the menu");
        require(view["surface"] == "pause" && view["active"], "Wrong surface published");
        require(control(view, "pause.resume")["stock"] == "resume", "Resume lost its typed stock route");
        require(host.readyMessage(ready(view), scope), "Current pause hello refused");
        require(!host.readyMessage(Json{{"protocol", 1}, {"session", scope.nonce}, {"event", "ready"}}.dump(), scope),
            "Legacy frontend hello acknowledged pause");
        auto wrongHello = Json::parse(ready(view));
        wrongHello["generation"] = "0";
        require(!host.readyMessage(wrongHello.dump(), scope), "Old view acknowledged pause");
        wrongHello = Json::parse(ready(view)); wrongHello["surface"] = "results";
        require(!host.readyMessage(wrongHello.dump(), scope), "Other movie acknowledged pause");
        auto legacy = Json::parse(command(view, "pause.return")); legacy.erase("surface");
        require(!host.select(legacy.dump(), scope, state, true).accepted, "Legacy click reached match");
        auto result = host.select(command(view, "pause.return"), scope, state, true);
        require(result.accepted && result.kind == CareerLayoutEffectKind::Navigate && result.action.empty(),
            "Unfinished return skipped confirmation");
        auto confirm = host.publish(scope, state, 101);
        require(control(confirm, "match.confirm_return")["return_commit"] == true &&
            control(confirm, "match.cancel_return")["return_commit"] == false, "Commit hint did not distinguish confirmation from Back");
        auto changed = state; changed["session"]["id"] = "different-activity";
        require(!host.select(command(confirm, "match.confirm_return"), scope, changed, true).accepted,
            "Old confirmation abandoned a changed activity");
        result = host.select(command(confirm, "match.confirm_return"), scope, state, true);
        require(result.accepted && result.action == "return_hub" && result.payload["abandon"] == true &&
            result.payload["expected_session_id"] == "activity-1", "Confirmed return lost bound identity");
        state["session"]["can_exit"] = false;
        auto held = host.publish(scope, state, 101.1, {}, {}, true);
        require(held["return_pending"] == true && held["return_hold"] == true &&
            control(held, "pause.resume")["enabled"] == false && control(held, "pause.options")["enabled"] == false,
            "Committed Return did not hold stock closing routes");
        require(!host.select(command(held, "pause.resume"), scope, state, true).accepted &&
            !host.select(command(held, "match.quit"), scope, state, true).accepted,
            "Held route or unsafe Quit dispatched");
        auto released = host.publish(scope, state, 101.2, {}, {}, true, Json::object(), false, false);
        require(released["return_hold"] == false && released["return_pending"] == true &&
            released["generation"] != held["generation"] && control(released, "pause.resume")["enabled"] == true,
            "Uncertain outcome did not release hold without losing pending intent");
        require(!host.select(command(held, "pause.resume"), scope, state, true).accepted,
            "Old held generation replayed after release");
        state["error"] = "Save unavailable";
        state["session"]["can_exit"] = true;
        auto recovery = host.publish(scope, state, 101.3, {}, {}, true);
        require(recovery["return_hold"] == false && control(recovery, "results.retry_save")["enabled"] == true &&
            control(recovery, "match.quit")["return_commit"] == false, "Save error trapped recovery controls");
        result = host.select(command(recovery, "match.quit"), scope, state, true);
        require(result.accepted && result.action == "quit_game" && result.payload.empty(),
            "Recovery Quit did not use the fixed safe dispatch");
        state["error"] = "";
        auto staleScope = scope; staleScope.surface = NativeMenuSurface::Results;
        require(!host.readyMessage(ready(confirm), staleScope), "Pause readiness leaked into results");
        scope = staleScope; ++scope.generation;
        require(host.open(scope, state), "Results did not open");
        auto unsaved = host.publish(scope, state, 102);
        require(control(unsaved, "results.return")["enabled"] == false, "Unsaved result allowed return");
        require(!host.select(command(unsaved, "results.return"), scope, state, true).accepted,
            "Disabled return dispatched");
        state["error"] = "Save unavailable";
        auto failedSave = host.publish(scope, state, 102);
        require(control(failedSave, "results.retry_save")["enabled"] == true,
            "Save failure did not offer retry");
        auto changedResult = state; changedResult["session"]["id"] = "new-activity";
        require(!host.select(command(failedSave, "results.retry_save"), scope, changedResult, true).accepted,
            "Old results retried a new match");
        result = host.select(command(failedSave, "results.retry_save"), scope, state, true);
        require(result.accepted && result.action == "retry_result_save" &&
            result.payload["expected_session_id"] == "activity-1" &&
            result.payload["expected_fixture_id"] == "career-1:s1:league:1:0", "Save retry lost match identity");
        state["error"] = "";
        state["session"]["state"] = "Career Ready";
        state["career"]["pending_session"] = nullptr;
        state["latest_result"] = {{"session_id", "activity-1"}, {"fixture_id", "other-fixture"}};
        auto mismatch = host.publish(scope, state, 103);
        require(control(mismatch, "results.return")["enabled"] == false, "Other fixture unlocked results");
        state["latest_result"]["fixture_id"] = state["session"]["fixture_id"];
        auto saved = host.publish(scope, state, 104);
        require(control(saved, "results.return")["return_commit"] == true, "Saved Return lacked immediate commit hint");
        require(control(saved, "results.return")["enabled"] == true, "Saved result did not unlock return");
        require(!host.readyMessage(ready(unsaved), scope), "Old result view acknowledged saved controls");
        result = host.select(command(saved, "results.return"), scope, state, true);
        require(result.accepted && result.action == "return_hub" && result.payload["abandon"] == false,
            "Saved result did not return through service");
        scope.surface = NativeMenuSurface::Pause; ++scope.generation;
        state["session"]["kind"] = "training"; state["session"]["state"] = "training";
        state["session"]["fixture_id"] = nullptr;
        require(host.open(scope, state), "Lesson pause did not open");
        auto lesson = host.publish(scope, state, 105);
        result = host.select(command(lesson, "pause.retry"), scope, state, true);
        require(result.accepted && result.action == "retry_lesson" && result.payload["expected_session_id"] == "activity-1",
            "Lesson retry lost the current activity");
        require(host.open(scope, state), "Lesson reopen failed");
        lesson = host.publish(scope, state, 106);
        auto offlineLost = scope; offlineLost.online = true;
        require(!host.select(command(lesson, "pause.retry"), offlineLost, state, true).accepted,
            "Online scope accepted a lesson action");
        std::string unicode; for (int i = 0; i < 200; ++i) unicode += u8"\u754c";
        state["error"] = unicode;
        require(Json::parse(host.publish(scope, state, 107).dump()).is_object(), "Feedback split UTF-8");
        std::cout << "Native pause/results scope, confirmation, saved result, and retry checks passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
