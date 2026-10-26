#include "LocalBridge.h"
#include <fstream>
#include <iostream>
#include <map>
#include <stdexcept>
#ifdef _WIN32
#include <chrono>
#include <thread>
#include <windows.h>
#endif

static void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
int main() {
    using namespace mct;
#ifdef _WIN32
    const auto id = newId();
    const auto root = std::filesystem::temp_directory_path() /
        (std::wstring(L"MCT-case-\u00e9-") + std::wstring(id.begin(), id.end()));
#else
    const auto root = std::filesystem::temp_directory_path() / ("mct-bridge-" + newId());
#endif
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
#ifdef _WIN32
        // A writer can hold DELETE access while allowing other readers. CRT
        // ifstream opens without FILE_SHARE_DELETE, which makes poll fail here.
        HANDLE deletingState = CreateFileW((root / "state.json").c_str(), DELETE,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
            OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        require(deletingState != INVALID_HANDLE_VALUE, "Could not hold the state replacement handle");
        const bool readDuringReplace = bridge.poll();
        CloseHandle(deletingState);
        require(readDuringReplace, "State polling failed during an allowed Windows replacement handle");
#endif
        require(bridge.poll(), "Published state was not read");
        require(bridge.poll(), "Unchanged fresh state cache failed");
        require(!bridge.poll(now + 6), "Unchanged cached state bypassed expiry");
        require(bridge.poll(), "Fresh state did not recover after cached expiry");
        require(!bridge.send("online_request"), "Online command accepted");
        require(!bridge.send("execute", {{"command", "bad"}}), "Arbitrary execution accepted");
        require(!bridge.send("unknown_catalog_action", {{"source", "steam_maps"}}),
                "Unknown catalog action accepted");
        require(!bridge.send("play_match", "not-an-object"), "Invalid payload accepted");
        std::map<std::string, Json> expectedCommands = {
            {"play_match", Json::object()},
            {"community_browse", {{"source", "steam_maps"}, {"page", 1}, {"query", ""}}},
            {"community_browse_cancel", Json::object()},
            {"community_open_source", {{"source", "bakkes_maps"}}},
            {"community_open_item", {{"source", "steam_maps"}, {"id", 1520915243}}},
            {"community_select_plugin", {{"source", "bakkes_plugins"}, {"id", 1520915243}}},
        };
        for (const auto& [action, payload] : expectedCommands)
            require(bridge.send(action, payload), "Allowed offline bridge command rejected");
        size_t commands = 0;
        std::map<std::string, size_t> observedActions;
        for (const auto& entry : std::filesystem::directory_iterator(root / "commands")) {
            require(entry.path().extension() == ".json", "Partial command leaked");
            std::ifstream file(entry.path()); Json command; file >> command;
            const auto action = stringValue(command, "action");
            require(command["session"] == valid["bridge_session"], "Command bridge session mismatch");
            require(expectedCommands.count(action) == 1, "Unexpected command was written");
            require(command["payload"] == expectedCommands.at(action), "Command payload changed while writing");
            require(stringValue(command, "id").size() == 36, "Canonical UUID missing");
            ++observedActions[action];
            ++commands;
        }
        require(commands == expectedCommands.size(), "Wrong command count");
        for (const auto& [action, _payload] : expectedCommands)
            require(observedActions[action] == 1, "Expected bridge action was not written exactly once");
        bridge.publishStatus({{"online", false}});
        require(std::filesystem::exists(root / "plugin-status.json"), "Runtime status missing");
#ifdef _WIN32
        HANDLE statusReader = CreateFileW((root / "plugin-status.json").c_str(), GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        require(statusReader != INVALID_HANDLE_VALUE, "Could not hold a reader on status");
        std::thread releaseReader([statusReader]() {
            std::this_thread::sleep_for(std::chrono::milliseconds(60));
            CloseHandle(statusReader);
        });
        bool statusPublished = true;
        try { bridge.publishStatus({{"online", false}}); }
        catch (...) { statusPublished = false; }
        releaseReader.join();
        require(statusPublished, "Brief Windows status read lock broke atomic publication");
#endif
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
