#include "NativeMovieProtocol.h"
#include <iostream>
#include <stdexcept>

using namespace mct;
static void require(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }
static CareerLayoutScope scope() { return {true, true, true, false, "native-test-session", 1}; }
static Json state() {
    return {{"protocol", 1}, {"offline", true}, {"bridge_session", "native-test-session"},
        {"setup_required", false}, {"session", {{"state", "Career Ready"}, {"busy", false}}}};
}
static std::string command(const Json& view, const std::string& id) {
    for (const auto& item : view.at("controls")) if (item.at("id") == id)
        return Json{{"protocol", 1}, {"session", view.at("session")},
            {"generation", view.at("generation")}, {"revision", item.at("revision")}, {"control", id}}.dump();
    throw std::runtime_error("Control not published");
}

int main() {
    try {
        NativeMovieProtocol protocol;
        auto live = scope();
        auto data = state();
        require(protocol.open(live, data), "Owned movie did not open");
        auto first = protocol.publish(live, data, 100);
        require(first.at("active") && first.at("controls").size() == 7, "Seven native controls missing");
        require(!first.at("production_ready") && !first.at("runtime_verified"), "Compatibility falsely granted");
        auto repeat = protocol.publish(live, data, 101);
        require(first.at("generation") == repeat.at("generation"), "Heartbeat rebuilt focus generation");
        const auto training = command(first, NativeCareerLayout::kTraining);
        require(!protocol.select(training, live, data, false).accepted, "Unrelated callback dispatched");
        auto stale = live;
        stale.online = true;
        require(!protocol.select(training, stale, data, true).accepted, "Online click accepted");
        auto wrong = Json::parse(training);
        wrong["session"] = "other-session";
        require(!protocol.select(wrong.dump(), live, data, true).accepted, "Wrong session accepted");
        wrong = Json::parse(training);
        wrong["payload"] = {{"action", "play_match"}};
        require(!protocol.select(wrong.dump(), live, data, true).accepted, "Caller payload accepted");
        auto selected = protocol.select(training, live, data, true);
        require(selected.accepted && selected.kind == CareerLayoutEffectKind::Navigate, "Training route failed");
        require(!protocol.select(training, live, data, true).accepted, "Duplicate click accepted");
        auto next = protocol.publish(live, data, 102);
        require(next.at("generation") != first.at("generation"), "Navigation kept stale generation");
        require(!protocol.select(training, live, data, true).accepted, "Old page click accepted");
        auto lost = live;
        lost.fresh = false;
        auto inactive = protocol.publish(lost, data, 103);
        require(!inactive.at("active") && inactive.at("controls").empty(), "Stale view remained active");
        require(!protocol.select(training, live, data, true).accepted, "Invalidation retained a click");
        require(protocol.open(live, data), "Reopen failed");
        auto reopened = protocol.publish(live, data, 104);
        require(reopened.at("generation") != first.at("generation"), "Reopen reused a generation");
        auto exit = command(reopened, NativeCareerLayout::kExit);
        auto effect = protocol.select(exit, live, data, true);
        require(effect.accepted && effect.action == "quit_game", "Exit did not reach fixed bridge action");
        require(effect.payload.empty(), "Exit carried arbitrary data");
        require(!protocol.select(exit, live, data, true).accepted, "Exit repeated");
        std::cout << "Native movie protocol checks passed; no game was launched.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
