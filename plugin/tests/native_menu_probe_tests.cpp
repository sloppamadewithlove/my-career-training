#include "NativeMenuProbe.h"
#include "ExecutableHash.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

namespace fs = std::filesystem;

static void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
static mct::Json readTrace(const fs::path& path) {
    std::ifstream stream(path);
    return mct::Json::parse(stream);
} // Close the Windows reader before any replacement or cleanup.

int main() {
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const fs::path directory = fs::temp_directory_path() / ("mct-native-probe-" + std::to_string(unique));
    fs::create_directories(directory);
    try {
        mct::LocalBridge bridge(directory);
        mct::NativeMenuProbe probe;
        mct::NativeProbeScope scope{true, true, false,
            "bf8c5a7b-53a8-41bc-8733-2ec57efcc496", "250923.46921.469711", "", "229"};

        auto unsafe = scope;
        unsafe.owned = false;
        require(!probe.start(unsafe, 100.0), "An unowned game started a probe");
        require(!probe.active(), "Unsafe start became active");
        require(probe.start(scope, 100.0), "Owned offline probe did not start");
        require(!probe.observe(scope, "account=private", "MainMenu", false, 100.1),
                "Unlisted event was recorded");
        require(!probe.observe(scope, "menu_stack_transition", "My\nProfile", false, 100.2),
                "Control characters entered trace");
        require(probe.observe(scope, "menu_stack_transition", "MainMenu", false, 100.3),
                "Menu transition was not recorded");
        require(probe.observe(scope, "Function TAGame.GFxData_MenuStack_TA.ButtonTriggered",
                              "PlayMenu", false, 100.4), "Named hook event was not recorded");
        require(probe.eventCount() == 2, "Invalid observations were retained");
        require(probe.stopToBridge(scope, 101.0, bridge), "Explicit stop did not publish trace");
        require(!probe.active() && probe.eventCount() == 0, "Stop retained private trace in memory");
        const auto path = directory / mct::NativeMenuProbe::kOutputName;
        require(fs::exists(path), "Trace did not use the fixed bridge filename");
        const auto trace = readTrace(path);
        require(trace["native_mutations"] == false, "Trace claimed a game modification");
        require(trace["scope"]["owned_offline_session"] == true, "Trace omitted offline scope");
        require(trace["scope"]["executable_sha256"].is_null(), "Unverified executable hash was fabricated");
        require(trace["events"].size() == 2, "Trace event count changed on export");
        require(trace.dump().find("account=private") == std::string::npos,
                "Rejected account text leaked into trace");

        fs::remove(path);
        require(probe.start(scope, 200.0), "Second probe did not start");
        probe.observe(scope, "menu_stack_transition", "MainMenu", false, 200.1);
        auto online = scope;
        online.online = true;
        require(!probe.observe(online, "menu_stack_transition", "MainMenu", false, 200.2),
                "Online transition was recorded");
        require(probe.eventCount() == 0, "Online transition did not erase trace");
        require(!probe.stopToBridge(scope, 200.3, bridge), "Erased trace was published");
        require(!fs::exists(path), "Online trace reached disk");

        require(probe.start(scope, 300.0), "Third probe did not start");
        auto changedSession = scope;
        changedSession.sessionNonce = "36e10d11-5e67-4998-9231-dc5c76723939";
        require(!probe.observe(changedSession, "menu_stack_transition", "MainMenu", false, 300.1),
                "Changed bridge nonce was recorded");
        require(probe.eventCount() == 0, "Changed nonce did not erase trace");

        require(probe.start(scope, 400.0), "Duration probe did not start");
        require(!probe.observe(scope, "menu_stack_transition", "MainMenu", false, 520.0),
                "Duration limit recorded a late event");
        require(!probe.active(), "Duration limit left collection running");
        require(probe.hasTrace(), "Duration-limited empty trace was lost before stop");
        auto stale = scope;
        stale.fresh = false;
        require(!probe.observe(stale, "", "", false, 520.05),
                "Stale bridge observation was accepted");
        require(!probe.hasTrace(), "Stale bridge did not erase bounded empty trace");
        require(!probe.stopToBridge(scope, 520.1, bridge), "Stale bounded trace was exported");
        require(!fs::exists(path), "Stale bounded trace reached disk");

        require(probe.start(scope, 530.0), "Cancel probe did not start");
        probe.observe(scope, "menu_stack_transition", "MainMenu", false, 530.1);
        probe.clear();
        require(!probe.hasTrace() && !probe.stopToBridge(scope, 530.2, bridge),
                "Cancelled trace remained exportable");
        require(!fs::exists(path), "Cancelled trace reached disk");

        auto hashedScope = scope;
        hashedScope.executableSha256 = std::string(64, 'a');
        require(probe.start(hashedScope, 540.0), "Hashed probe did not start");
        auto changedHash = hashedScope;
        changedHash.executableSha256 = std::string(64, 'b');
        require(!probe.observe(changedHash, "menu_stack_transition", "MainMenu", false, 540.1),
                "Mismatched executable hash was accepted");
        require(!probe.hasTrace() && !probe.stopToBridge(hashedScope, 540.2, bridge),
                "Mismatched executable trace remained exportable");

        require(probe.start(scope, 550.0), "Save retry probe did not start");
        probe.observe(scope, "menu_stack_transition", "MainMenu", false, 550.1);
        fs::create_directory(path);
        bool writeFailed = false;
        try { probe.stopToBridge(scope, 550.2, bridge); }
        catch (const std::exception&) { writeFailed = true; }
        require(writeFailed && probe.hasTrace(), "Failed export discarded the trace before retry");
        require(!probe.active(), "Failed export kept collecting after Stop");
        probe.observe(scope, "menu_stack_transition", "PlayMenu", false, 550.25);
        require(probe.eventCount() == 1, "Failed export changed the frozen trace");
        fs::remove(path);
        require(probe.stopToBridge(scope, 550.3, bridge), "Retry did not publish retained trace");
        require(readTrace(path)["events"].size() == 1, "Retry changed captured menu events");
        fs::remove(path);

#ifdef _WIN32
        const auto hashPath = directory / "sha256-vector.txt";
        {
            std::ofstream stream(hashPath, std::ios::binary);
            stream << "abc";
        }
        require(mct::sha256File(hashPath) ==
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
                "Windows executable hash does not match the SHA-256 vector");
        fs::remove(hashPath);
#endif

        require(probe.start(scope, 600.0), "Second duration probe did not start");
        require(!probe.observe(scope, "", "", false, 720.0),
                "Duration limit accepted empty observation");
        require(probe.stopToBridge(scope, 720.1, bridge), "Duration-limited trace was lost");
        require(readTrace(path)["finish_reason"] == "duration_limit",
                "Duration stop reason was not recorded");

        fs::remove(path);
        require(probe.start(scope, 800.0), "Count probe did not start");
        for (std::size_t i = 0; i < mct::NativeMenuProbe::kMaxEvents + 30; ++i)
            probe.observe(scope, "menu_stack_transition", "MainMenu", false, 800.0 + i * 0.001);
        require(!probe.active(), "Event limit left collection running");
        require(probe.eventCount() == mct::NativeMenuProbe::kMaxEvents,
                "Event limit exceeded or undercounted");
        require(probe.stopToBridge(scope, 802.0, bridge), "Count-limited trace was lost");
        const auto countTrace = readTrace(path);
        require(countTrace["finish_reason"] == "event_limit", "Event limit reason missing");
        require(countTrace["events"].size() == mct::NativeMenuProbe::kMaxEvents,
                "Export exceeded event limit");

        fs::remove_all(directory);
        std::cout << "Native menu probe scope, privacy, limits and fixed export passed.\n";
        return 0;
    } catch (const std::exception& error) {
        fs::remove_all(directory);
        std::cerr << error.what() << '\n';
        return 1;
    }
}
