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
int main() {
    try {
        forfeitChecks();
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
