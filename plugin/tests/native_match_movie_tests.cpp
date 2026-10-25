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
int main() {
    try {
        CareerLayoutScope scope{true, true, true, false, "test-owned-native-session", 1, NativeMenuSurface::Pause};
        Json state = {{"protocol", 1}, {"offline", true}, {"bridge_session", scope.nonce},
            {"session", {{"id", "activity-1"}, {"fixture_id", "career-1:s1:league:1:0"}, {"kind", "career"},
                {"state", "Playing"}, {"worker_running", true}, {"busy", false}}},
            {"career", {{"pending_session", {{"fixture_id", "career-1:s1:league:1:0"}, {"session_id", "activity-1"}}}}}};
        NativeMovieProtocol host;
        require(host.open(scope, state), "Pause did not open");
        auto view = host.publish(scope, state, 100);
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
        auto changed = state; changed["session"]["id"] = "different-activity";
        require(!host.select(command(confirm, "match.confirm_return"), scope, changed, true).accepted,
            "Old confirmation abandoned a changed activity");
        result = host.select(command(confirm, "match.confirm_return"), scope, state, true);
        require(result.accepted && result.action == "return_hub" && result.payload["abandon"] == true &&
            result.payload["expected_session_id"] == "activity-1", "Confirmed return lost bound identity");
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
