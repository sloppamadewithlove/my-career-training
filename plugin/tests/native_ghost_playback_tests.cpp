#include "NativeGhostPlayback.h"
// Transport mode deliberately uses the real companion producer adapter.
#include "NativeGhostRecording.h"
#include <iostream>
#include <stdexcept>
#include <chrono>
#include <algorithm>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#endif

using namespace mct;
static constexpr const char* generation = "00000000-0000-4000-8000-000000000001";
static void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }

static NativeDrawObservation observation() {
    NativeDrawObservation out;
    out.identity = {42, 100, std::string("synthetic-owned-nonce:") + generation, 1, 2, 3, 0, 0};
    out.ownedOffline = out.fresh = out.buildVerified = out.workerTraining = true;
    out.carObserved = out.ballObserved = out.actionsObserved = true;
    out.gameSeconds = 50;
    out.carPosition = {100, 200, 17};
    out.ballPosition = {200, 300, 100};
    return out;
}

static Json state(std::uint64_t sequence = 1, std::uint64_t received = 1000) {
    return {{"bridge_session", "synthetic-owned-nonce"}, {"published_at", 100},
        {"session", {{"id", "synthetic-worker"}}}, {"telemetry", {{"native_ghost_source", {
            {"session_id", "synthetic-worker"}, {"sequence", sequence},
            {"bridge_session", "synthetic-owned-nonce"}, {"reset_generation", generation},
            {"reset_observed", true},
            {"received_uptime_ms", received}, {"attempt_id", "synthetic-attempt"},
            {"packet_gap", false}, {"active", true}}}}}};
}

static Json transport(NativeGhostPlayback& playback, const Json& item) {
    const auto& snapshot = item.at("state");
    auto live = observation();
    LocalBridge bridge(std::filesystem::u8path(item.at("bridge_directory").get<std::string>()));
    const auto nonce = stringValue(snapshot, "bridge_session");
    live.identity.nonce = nonce + ":" + bridge.nativeGhostResetGeneration(
        stringValue(objectValue(snapshot, "session"), "id"), nonce);
    const auto frame = playback.update(snapshot, live, nativeGhostSampleFromState(snapshot),
        item.at("now").get<double>(), item.at("uptime_ms").get<std::uint64_t>());
    return {{"visible", bool(frame)}, {"observed_at", frame ? Json(frame->observedAt) : Json(nullptr)}};
}

int main(int argc, char** argv) {
    try {
        if (argc > 1 && std::string(argv[1]) == "--clock") {
#ifdef _WIN32
            std::cout << GetTickCount64() << '\n';
#else
            std::cout << "null\n";
#endif
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--live-transport") {
            NativeGhostPlayback playback;
            std::string line;
            while (std::getline(std::cin, line))
                std::cout << transport(playback, Json::parse(line)).dump() << std::endl;
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--fence-benchmark") {
            Json request;
            std::cin >> request;
            LocalBridge bridge(std::filesystem::u8path(request.at("bridge_directory").get<std::string>()));
            std::vector<double> micros;
            for (int i = 0; i < 2000; ++i) {
                const auto start = std::chrono::steady_clock::now();
                require(!bridge.nativeGhostResetGeneration(request.at("session_id"), request.at("bridge_session")).empty(),
                    "Fence benchmark scope was invalid");
                micros.push_back(std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - start).count());
            }
            std::sort(micros.begin(), micros.end());
            std::cout << Json{{"median_us", micros[1000]}, {"p95_us", micros[1900]}, {"reads", micros.size()}}.dump() << '\n';
            return 0;
        }
        if (argc > 1) {
            Json request;
            std::cin >> request;
            NativeGhostPlayback playback;
            Json results = Json::array();
            for (const auto& item : request) {
                results.push_back(transport(playback, item));
            }
            std::cout << results.dump() << '\n';
            return 0;
        }
        NativeGhostPlayback host;
        auto live = observation();
        NativeGhostRenderSample sample;
        sample.recordedSeconds = .25;
        sample.car.position = {100, 200, 300};
        sample.ballPosition = std::array<float, 3>{200, 250, 350};
        sample.actions = NativeDrawActions{};
        auto first = host.update(state(), live, sample, 100, 1000);
        require(bool(first), "Fresh source callback receipt did not produce a frame");
        auto heartbeat = state();
        heartbeat["published_at"] = 999999;
        auto same = host.update(heartbeat, live, sample, 100.05, 1050);
        require(same == first && same->observedAt == 100, "Bridge heartbeat restamped a cached packet");
        require(!host.update(heartbeat, live, sample, 100.1, 1100), "Heartbeat extended expired source");
        require(!host.update(state(), live, sample, 100.11, 1110), "Expired cached sample revived");
        const auto second = host.update(state(2, 1111), live, sample, 100.111, 1111);
        require(bool(second), "New callback did not recover after expiry");
        require(!nativeGhostRenderFrameCurrent(*first, second->lease, 100.111), "Old lease survived new sample");
        auto retry = state(3, 1120);
        retry["telemetry"]["native_ghost_source"]["attempt_id"] = "synthetic-retry";
        const auto retried = host.update(retry, live, sample, 100.12, 1120);
        require(retried && retried->lease.identity.epoch != second->lease.identity.epoch,
            "Whole lesson retry retained draw epoch");
        auto gap = state(4, 1130);
        gap["telemetry"]["native_ghost_source"]["packet_gap"] = true;
        require(!host.update(gap, live, sample, 100.13, 1130), "Packet gap produced a frame");
        require(!host.update(retry, live, sample, 100.14, 1140), "Out-of-order pre-gap packet revived");
        require(bool(host.update(state(5, 1141), live, sample, 100.141, 1141)), "Fresh packet recovery failed");
        auto changed = live;
        changed.identity.event = 4;
        require(!host.current(state(5, 1141), changed, 100.15, 1150), "Event loss between ticks retained scope");
        require(!host.update(state(5, 1141), live, sample, 100.16, 1160), "Revoked cached packet revived");
        for (auto received : {std::uint64_t{900}, std::uint64_t{1001}}) {
            NativeGhostPlayback delayed;
            require(!delayed.update(state(1, received), live, sample, 100, 1000), "Delayed/future callback receipt admitted");
        }
        for (const auto& key : {"received_uptime_ms", "attempt_id", "sequence", "session_id", "packet_gap", "active"}) {
            NativeGhostPlayback missing;
            auto invalid = state();
            invalid["telemetry"]["native_ghost_source"].erase(key);
            require(!missing.update(invalid, live, sample, 100, 1000), "Missing source metadata admitted");
        }
        for (auto field : {&NativeDrawObservation::ownedOffline, &NativeDrawObservation::fresh,
                &NativeDrawObservation::buildVerified, &NativeDrawObservation::workerTraining}) {
            NativeGhostPlayback denied;
            auto invalid = live;
            invalid.*field = false;
            require(!denied.update(state(), invalid, sample, 100, 1000), "Source bypassed actual scope gate");
        }
        NativeGhostPlayback off;
        require(bool(off.update(state(), live, sample, 100, 1000)), "Off fixture failed");
        require(!off.update(state(2, 1010), live, {}, 100.01, 1010), "Hidden recording remained visible");
        require(!off.update(state(), live, sample, 100.02, 1020), "Old On snapshot revived after Off");
        std::cout << "Native ghost callback uptime, heartbeat age, retry, order, gap and scope tests passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
