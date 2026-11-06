#include "NativeGhostRecording.h"
#include <iostream>
#include <fstream>
#include <stdexcept>

using namespace mct;
static void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }

int main(int argc, char** argv) {
    try {
        if (argc == 2) {
            std::ifstream stream(argv[1]);
            const auto state = Json::parse(stream);
            const auto sample = nativeGhostSampleFromState(state);
            require(sample.has_value(), "Production worker/bridge payload refused");
            std::cout << Json{{"time", sample->recordedSeconds}, {"position", sample->car.position},
                {"orientation", sample->car.orientation}, {"ball_position", *sample->ballPosition},
                {"jump", sample->actions->jump}, {"boost", sample->actions->boost}}.dump() << '\n';
            return 0;
        }
        // Synthetic existing-worker payload; never distributed as a teaching trace.
        const Json actions{{"throttle", 1.0}, {"steer", -.5}, {"pitch", .25}, {"yaw", 0},
            {"roll", 1}, {"jump", true}, {"boost", true}, {"handbrake", false}};
        Json state{{"session", {{"id", "lesson-session"}, {"kind", "training"},
                {"state", "training"}, {"worker_running", true}}},
            {"telemetry", {{"lesson_id", "flip-reset"}, {"ghost_practice_support", {{"supported", true}}},
                {"ghost_practice_pending", false}, {"ghost_practice", {{"lesson_id", "flip-reset"},
                    {"available", true}, {"enabled", true}, {"visible", true}, {"cursor", .5},
                    {"status", "playing"}, {"player_input_applied", false}, {"coach_actions", actions},
                    {"provenance", {{"compatibility", true}, {"outcome", "success"}}},
                    {"pose", {{"time", .5}, {"position", {100, 200, 500}},
                        {"quaternion", {0, 1, 0, 0}}, {"ball_position", {100, 200, 600}},
                        {"actions", actions}}}}}}}};
        const auto sample = nativeGhostSampleFromState(state);
        require(sample.has_value(), "Current recording payload refused");
        require(sample->car.orientation == std::array<float, 4>{1, 0, 0, 0}, "wxyz was not converted to xyzw");
        const auto mesh = prepareNativeGhostProxy(sample->car);
        require(mesh && mesh->vertices[4][2] == 458, "Converted upside-down car has wrong orientation");
        require(sample->recordedSeconds == .5 && sample->actions->boost && sample->actions->jump &&
            sample->ballPosition == std::optional<std::array<float, 3>>{{100, 200, 600}},
            "Car, ball, cursor and held actions lost synchronization");
        for (int failure = 0; failure < 16; ++failure) {
            auto bad = state;
            auto& telemetry = bad["telemetry"];
            auto& practice = telemetry["ghost_practice"];
            auto& pose = practice["pose"];
            if (failure == 0) practice["enabled"] = false;
            if (failure == 1) practice["visible"] = false;
            if (failure == 2) practice["lesson_id"] = "speed-flip";
            if (failure == 3) bad["session"]["kind"] = "career";
            if (failure == 4) bad["session"]["worker_running"] = false;
            if (failure == 5) practice["provenance"]["compatibility"] = false;
            if (failure == 6) practice["provenance"]["outcome"] = "failed";
            if (failure == 7) telemetry["reference_capture"] = {{"active", false}};
            if (failure == 8) telemetry["ghost_practice_pending"] = true;
            if (failure == 9) practice["cursor"] = .6;
            if (failure == 10) pose.erase("ball_position");
            if (failure == 11) pose["quaternion"] = {0, 0, 0, 0};
            if (failure == 12) pose["actions"]["jump"] = 1;
            if (failure == 13) practice["coach_actions"]["boost"] = false;
            if (failure == 14) pose["position"][0] = true;
            if (failure == 15) practice["status"] = "capture_gap";
            require(!nativeGhostSampleFromState(bad), "Unsafe recording payload was accepted");
        }
        state["telemetry"]["ghost_practice"]["pose"]["quaternion"] = {1, 0, 0, 0};
        const auto upright = nativeGhostSampleFromState(state);
        require(upright && upright->car.orientation == std::array<float, 4>{0, 0, 0, 1},
            "Identity recording quaternion did not remain upright");
        std::cout << "native ghost recording tests passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
