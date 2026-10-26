#include "NativeTrainingPackHost.h"

#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using mct::Json;
using mct::NativeTrainingPackHost;
using mct::NativeTrainingPackObservation;

namespace {
const std::string nonce = "45234854-6e9c-4af5-9c50-e9347f375140";
const std::string session = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const std::string requestId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

NativeTrainingPackObservation ready() {
    NativeTrainingPackObservation observation;
    observation.processAvailable = true;
    observation.ownedOffline = true;
    observation.fresh = true;
    observation.movieReady = true;
    observation.buildVerified = true;
    observation.frontend = true;
    observation.nonce = nonce;
    observation.pid = 888;
    observation.created = 1234567890.125;
    observation.now = 100;
    return observation;
}

Json request(const std::string& pack = "powershot-practice") {
    return {{"protocol", 1}, {"bridge_session", nonce},
            {"training_pack_request", {{"pack_id", pack}, {"session_id", session},
                {"request_id", requestId}, {"nonce", nonce}, {"pid", 888},
                {"start_identity", "1234567890.125"}}}};
}

void testCatalogAndNormalization() {
    require(mct::LocalBridge::allowedAction("start_training_pack"), "native bridge allowlist");
    require(mct::kNativeTrainingPacks.size() == 6, "catalog size");
    require(mct::nativeTrainingPackCode("powershot-practice") == "C9E4-0F05-B71A-C322", "gold code");
    require(mct::nativeTrainingPackCode("powershots") == "7028-5E10-88EF-E83E", "powershots code");
    require(mct::nativeTrainingPackCode("powershot-training") == "7EB0-B25B-689D-3413", "training code");
    require(mct::nativeTrainingPackCode("power-shot-air-roll-shot") == "1C4E-D311-1506-B6C1", "air roll code");
    require(mct::nativeTrainingPackCode("powerclears-on-wall") == "5053-597D-C47B-B5B0", "wall code");
    require(mct::nativeTrainingPackCode("powershots-super-champion") == "0390-AED7-109D-8770", "gc code");
    require(mct::nativeTrainingPackCode("unknown").empty(), "unknown id");
    require(mct::nativeTrainingPackCodesMatch("c9e40f05b71ac322", "C9E4-0F05-B71A-C322"), "supported format");
    require(!mct::nativeTrainingPackCodesMatch("C9E4-0F05-B71A-C323", "C9E4-0F05-B71A-C322"), "wrong code");
}

void testExactLoadAndOnceOnlyCommand() {
    std::vector<std::string> commands;
    auto observation = ready();
    NativeTrainingPackHost host([&](const std::string& value) { commands.push_back(value); });
    host.tick(request(), [&] { return observation; });
    require(commands == std::vector<std::string>{"load_training C9E4-0F05-B71A-C322"}, "exact command");
    require(host.status().at("status") == "pending", "pending after dispatch");
    observation.frontend = false;
    host.tick(request(), [&] { return observation; });
    require(commands.size() == 1 && host.status().at("status") == "pending", "generic game state is not success");
    observation.inCustomTraining = true;
    observation.loadedCode = "C9E4-0F05-B71A-C322";
    host.tick(request(), [&] { return observation; });
    require(commands.size() == 1 && host.status().at("status") == "loaded", "exact loaded ack");
    require(host.status().at("session_id") == session && host.status().at("request_id") == requestId, "tokens in ack");
    require(host.status().at("code") == "C9E4-0F05-B71A-C322", "code in ack");
    host.tick(request(), [&] { return observation; });
    require(commands.size() == 1, "loaded request not repeated");
}

void testLoadedPackMustRemainExactAndActive() {
    const auto load = [](NativeTrainingPackHost& host, NativeTrainingPackObservation& observation) {
        host.tick(request(), [&] { return observation; });
        observation.frontend = false;
        observation.inCustomTraining = true;
        observation.loadedCode = "C9E4-0F05-B71A-C322";
        host.tick(request(), [&] { return observation; });
        require(host.status().at("status") == "loaded", "exact pack loaded");
    };
    {
        auto observation = ready();
        NativeTrainingPackHost host([](const std::string&) {});
        load(host, observation);
        observation.loadedCode = "7028-5E10-88EF-E83E";
        host.tick(request(), [&] { return observation; });
        require(host.status().at("status") == "failed" &&
                host.status().at("reason") == "loaded_pack_changed", "changed loaded code refused");
    }
    {
        auto observation = ready();
        NativeTrainingPackHost host([](const std::string&) {});
        load(host, observation);
        observation.inCustomTraining = false;
        observation.loadedCode.clear();
        host.tick(request(), [&] { return observation; });
        require(host.status().at("status") == "failed" &&
                host.status().at("reason") == "loaded_pack_changed", "departure before Return refused");
    }
}

void testActiveMissingRequestFailsButClearedActivityCanRetire() {
    const auto loadedHost = [](NativeTrainingPackHost& host, NativeTrainingPackObservation& observation) {
        host.tick(request(), [&] { return observation; });
        observation.frontend = false;
        observation.inCustomTraining = true;
        observation.loadedCode = "C9E4-0F05-B71A-C322";
        host.tick(request(), [&] { return observation; });
        require(host.status().at("status") == "loaded", "loaded before retirement check");
    };
    {
        auto observation = ready();
        NativeTrainingPackHost host([](const std::string&) {});
        loadedHost(host, observation);
        auto missing = request();
        missing["training_pack_request"] = nullptr;
        missing["session"] = {{"id", session}};
        host.tick(missing, [&] { return observation; });
        require(host.status().at("status") == "failed" &&
                host.status().at("reason") == "active_request_missing", "active request removal fails closed");
    }
    {
        auto observation = ready();
        NativeTrainingPackHost host([](const std::string&) {});
        loadedHost(host, observation);
        auto returned = request();
        returned["training_pack_request"] = nullptr;
        returned["session"] = {{"id", nullptr}};
        host.tick(returned, [&] { return observation; });
        require(host.status().at("status") == "idle" &&
                host.status().at("reason") == "request_complete" && !host.active(),
                "Return clears request and session id before host retires");
    }
}

void testMalformedStaleAndForeignRequests() {
    for (int variant = 0; variant < 4; ++variant) {
        int commands = 0;
        auto state = request();
        auto observation = ready();
        if (variant == 0) state["training_pack_request"]["pack_id"] = "unknown";
        if (variant == 1) state["training_pack_request"]["command"] = "quit";
        if (variant == 2) state["training_pack_request"]["nonce"] = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
        if (variant == 3) state["training_pack_request"]["pid"] = 999;
        NativeTrainingPackHost host([&](const std::string&) { ++commands; });
        host.tick(state, [&] { return observation; });
        require(commands == 0 && host.status().at("status") == "failed", "bad request refused");
    }
}

void testWrongCodeTimeoutScopeAndResetNeverRetry() {
    {
        int commands = 0;
        auto observation = ready();
        NativeTrainingPackHost host([&](const std::string&) { ++commands; });
        host.tick(request(), [&] { return observation; });
        observation.frontend = false;
        observation.inCustomTraining = true;
        observation.loadedCode = "7028-5E10-88EF-E83E";
        host.tick(request(), [&] { return observation; });
        require(commands == 1 && host.status().at("status") == "failed", "wrong code failed");
        require(host.status().at("reason") == "loaded_code_mismatch", "wrong code reason");
    }
    {
        int commands = 0;
        auto observation = ready();
        NativeTrainingPackHost host([&](const std::string&) { ++commands; });
        host.tick(request(), [&] { return observation; });
        observation.frontend = false;
        observation.now = 121;
        host.tick(request(), [&] { return observation; });
        observation.inCustomTraining = true;
        observation.loadedCode = "C9E4-0F05-B71A-C322";
        host.tick(request(), [&] { return observation; });
        require(commands == 1 && host.status().at("reason") == "confirmation_timeout", "timeout no retry");
    }
    {
        int commands = 0;
        auto observation = ready();
        NativeTrainingPackHost host([&](const std::string&) { ++commands; });
        host.tick(request(), [&] { return observation; });
        observation.fresh = false;
        host.tick(request(), [&] { return observation; });
        observation = ready();
        host.tick(request(), [&] { return observation; });
        require(commands == 1 && host.status().at("reason") == "scope_lost", "scope loss no retry");
    }
    {
        int commands = 0;
        auto observation = ready();
        NativeTrainingPackHost host([&](const std::string&) { ++commands; });
        host.tick(request(), [&] { return observation; });
        host.reset();
        require(commands == 1, "reset has no command");
        host.tick(request(), [&] { return observation; });
        require(commands == 1 && host.status().at("reason") == "request_reused", "reset cannot repeat token");
    }
}
}

int main() {
    try {
        testCatalogAndNormalization();
        testExactLoadAndOnceOnlyCommand();
        testLoadedPackMustRemainExactAndActive();
        testActiveMissingRequestFailsButClearedActivityCanRetire();
        testMalformedStaleAndForeignRequests();
        testWrongCodeTimeoutScopeAndResetNeverRetry();
        std::cout << "native training pack host tests passed\n";
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
