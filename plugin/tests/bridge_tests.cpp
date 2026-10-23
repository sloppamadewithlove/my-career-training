#include "LocalBridge.h"
#include <fstream>
#include <iostream>
#include <stdexcept>

static void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
int main() {
    using namespace mct;
    const auto root = std::filesystem::temp_directory_path() / ("mct-bridge-" + newId());
    try {
        LocalBridge bridge(root);
        const double now = unixTime();
        Json valid = {{"protocol", 1}, {"offline", true}, {"bridge_session", "0123456789abcdef0123456789abcdef"}, {"published_at", now}};
        require(!bridge.poll(), "Missing state was accepted");
        require(LocalBridge::validState(valid, now), "Valid state rejected");
        require(!LocalBridge::validState(valid, now + 6), "Stale service accepted");
        auto online = valid; online["offline"] = false;
        require(!LocalBridge::validState(online, now), "Online state accepted");
        auto invalid = valid; invalid["bridge_session"] = "../../arbitrary/path";
        require(!LocalBridge::validState(invalid, now), "Invalid session accepted");
        LocalBridge::atomicWrite(root / "state.json", valid.dump());
        require(bridge.poll(), "Published state was not read");
        require(bridge.poll(), "Unchanged fresh state cache failed");
        require(!bridge.poll(now + 6), "Unchanged cached state bypassed expiry");
        require(bridge.poll(), "Fresh state did not recover after cached expiry");
        require(!bridge.send("online_request"), "Online command accepted");
        require(!bridge.send("execute", {{"command", "bad"}}), "Arbitrary execution accepted");
        require(!bridge.send("play_match", "not-an-object"), "Invalid payload accepted");
        require(bridge.send("play_match"), "Offline fixture command rejected");
        size_t commands = 0;
        for (const auto& entry : std::filesystem::directory_iterator(root / "commands")) {
            require(entry.path().extension() == ".json", "Partial command leaked");
            std::ifstream file(entry.path()); Json command; file >> command;
            require(command["session"] == valid["bridge_session"] && command["action"] == "play_match", "Command identity mismatch");
            require(stringValue(command, "id").size() == 36, "Canonical UUID missing");
            ++commands;
        }
        require(commands == 1, "Wrong command count");
        bridge.publishStatus({{"online", false}});
        require(std::filesystem::exists(root / "plugin-status.json"), "Runtime status missing");
        LocalBridge::atomicWrite(root / "state.json", "{broken");
        require(!bridge.poll() && !bridge.fresh(), "Malformed state did not fail closed");
        require(!bridge.send("play_match"), "Command sent after disconnect");
        std::filesystem::remove_all(root);
        std::cout << "Local bridge: stale/online/nonce/action/atomic command contracts passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::filesystem::remove_all(root);
        std::cerr << error.what() << '\n';
        return 1;
    }
}
