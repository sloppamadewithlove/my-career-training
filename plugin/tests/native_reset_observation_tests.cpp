#include "NativeResetObservation.h"
#include <iostream>
#include <limits>
#include <stdexcept>
using namespace mct;
static void check(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }
struct World {
    NativeResetObservation probe;
    Json request = {{"request_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"},
        {"nonce", "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"}, {"pid", 42u},
        {"start_identity", "100.000"}, {"issued_at", 10}, {"expires_at", 15}};
    NativeResetScope scope;
    NativeResetSample sample{2, 3, 10, 40, 10, 4};
    int scopes = 0, reads = 0;
    bool changeAfterRead = false, failRead = false;
    World() {
        scope.process.processAvailable = scope.process.ownedOffline = scope.process.fresh = true;
        scope.process.buildVerified = scope.process.inCustomTraining = true;
        scope.process.nonce = request["nonce"];
        scope.process.pid = 42; scope.process.created = 100;
        scope.paused = false; scope.event = 1; scope.car = 2; scope.ball = 3; scope.monotonic = 20;
        scope.controller = 4;
    }
    void tick(double wall = 11) {
        probe.tick(request, [&] { ++scopes; auto value = scope;
            if (changeAfterRead && reads) ++value.ball;
            return value;
        }, [&](const NativeResetScope& admitted) {
            check(admitted.car == scope.car && admitted.ball == scope.ball && admitted.event == scope.event,
                "Reader did not receive admitted actors");
            ++reads; if (failRead) throw std::runtime_error("reader"); return sample;
        }, wall);
    }
};
int main() {
    try {
        World idle; idle.request = nullptr; idle.tick();
        check(idle.scopes == 0 && idle.reads == 0, "Idle probe called readers");
        World w; w.tick();
        check(w.reads == 1 && w.probe.status()["samples"].size() == 1, "Valid request did not observe");
        check(w.probe.status()["reset_generation"].is_null() &&
            w.probe.status()["semantics_verified"] == false, "Raw samples gained reset authority");
        w.sample.worldSeconds = 0; w.sample.shotAttempt = 0; w.tick();
        check(w.probe.status()["samples"].size() == 2, "Raw reset-like values were rewritten or inferred");
        w.scope.monotonic = 24; w.tick(15); // Both clocks advance through the fixed deadline.
        check(w.probe.status()["status"] == "complete" && w.reads == 2, "Local deadline renewed");
        w.request["request_id"] = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"; w.scope.monotonic = 21; w.tick();
        check(w.reads == 2, "Retired probe rearmed");
        for (auto flag : {&NativeTrainingPackObservation::processAvailable,
                &NativeTrainingPackObservation::ownedOffline, &NativeTrainingPackObservation::fresh,
                &NativeTrainingPackObservation::buildVerified, &NativeTrainingPackObservation::inCustomTraining}) {
            World bad; bad.scope.process.*flag = false; bad.tick();
            check(bad.reads == 0, "Invalid scope reached data reader");
            bad.scope.process.*flag = true; bad.tick(); check(bad.reads == 0, "Rejected request rearmed");
        }
        for (auto flag : {&NativeTrainingPackObservation::online, &NativeTrainingPackObservation::replay,
                &NativeTrainingPackObservation::frontend}) {
            World bad; bad.scope.process.*flag = true; bad.tick();
            check(bad.reads == 0, "Unsafe mode reached reader");
        }
        World paused; paused.scope.paused = true; paused.tick(); check(paused.reads == 0, "Pause admitted");
        World changed; changed.changeAfterRead = true; changed.tick();
        check(changed.probe.status()["samples"].empty(), "Changed identity published data");
        World finite; finite.sample.remaining = std::numeric_limits<float>::infinity(); finite.tick();
        check(finite.probe.status()["samples"].empty(), "Nonfinite clock published");
        World thrown; thrown.failRead = true; thrown.tick(); thrown.failRead = false; thrown.tick();
        check(thrown.reads == 1, "Exception did not retire request");
        World regressed; regressed.tick(); regressed.scope.monotonic = 19; regressed.tick();
        check(regressed.reads == 1, "Monotonic regression reached reader");
        World changedRequest; changedRequest.tick(); changedRequest.request["expires_at"] = 16; changedRequest.tick(12);
        check(changedRequest.reads == 1, "Publication changed deadline");
        World stale; stale.tick(15); check(stale.reads == 0, "Expired request admitted");
        for (auto field : {&NativeResetSample::worldSeconds, &NativeResetSample::remaining,
                &NativeResetSample::totalPlayed}) {
            World bad; bad.sample.*field = std::numeric_limits<float>::quiet_NaN(); bad.tick();
            check(bad.probe.status()["samples"].empty(), "Nonfinite raw clock admitted");
        }
        for (auto field : {&NativeResetScope::event, &NativeResetScope::car, &NativeResetScope::ball,
                &NativeResetScope::controller}) {
            World bad; bad.tick(); ++(bad.scope.*field); bad.tick();
            check(bad.reads == 1, "Replaced wrapper reached sample reader");
        }
        World wrongPid; wrongPid.request["pid"] = 43u; wrongPid.tick();
        check(wrongPid.reads == 0, "Caller-selected process was admitted");
        World extra; extra.request["pointer"] = 123; extra.tick();
        check(extra.scopes == 0 && extra.reads == 0, "Extra payload reached native readers");
        World unknownCreated; unknownCreated.scope.process.created = std::numeric_limits<double>::quiet_NaN();
        unknownCreated.request["start_identity"] = ""; unknownCreated.tick();
        check(unknownCreated.reads == 0, "Unknown process creation admitted");
        World cancelled; cancelled.tick(); cancelled.probe.cancel(); cancelled.tick();
        check(cancelled.reads == 1, "Unload did not retire request");
        World raw;
        raw.sample.car = {{101, -202, 303}, {4, -5, 6}, {7, -8, 9}, {0.1f, 0.2f, 0.3f, 0.4f}, 41, true, false};
        raw.sample.ball = {{-1, 2, -3}, {-4, 5, -6}, {-7, 8, -9}, {-0.4f, -0.3f, -0.2f, -0.1f}, 42, false, true};
        raw.sample.controls = {-1, 1, -0.5f, 0.5f, 0.25f, -0.75f, 0.75f, true, false, false, true, true};
        raw.tick();
        const auto observed = raw.probe.status()["samples"][0];
        check(observed["car_rb_state"]["location"] == Json(raw.sample.car.location) &&
            observed["ball_rb_state"]["angular_velocity"] == Json(raw.sample.ball.angularVelocity) &&
            observed["car_rb_state"]["quaternion_xyzw"] == Json(raw.sample.car.quaternionXyzw) &&
            observed["ball_rb_state"]["quaternion_xyzw"] == Json(raw.sample.ball.quaternionXyzw) &&
            observed["car_rb_state"]["time"] == 41 && observed["ball_rb_state"]["new_data"] == true,
            "Raw body values or native quaternion order changed");
        check(observed["observed_controls"]["throttle"] == -1 &&
            observed["observed_controls"]["dodge_forward"] == -0.75f &&
            observed["observed_controls"]["boost"] == true &&
            observed["observed_controls"]["activate_boost"] == false &&
            observed["observed_controls"]["holding_boost"] == true &&
            observed["observed_controls"]["jump"] == false,
            "Observed controls were changed or raw boost flags collapsed");
        for (bool car : {false, true}) {
            for (int component = 0; component < 14; ++component) {
                World bad;
                auto& body = car ? bad.sample.car : bad.sample.ball;
                const float invalid = std::numeric_limits<float>::quiet_NaN();
                if (component < 3) body.location[component] = invalid;
                else if (component < 6) body.linearVelocity[component - 3] = invalid;
                else if (component < 9) body.angularVelocity[component - 6] = invalid;
                else if (component < 13) body.quaternionXyzw[component - 9] = invalid;
                else body.time = invalid;
                bad.tick();
                check(bad.probe.status()["samples"].empty(), "Nonfinite body component published");
            }
        }
        for (auto field : {&NativeResetControls::throttle, &NativeResetControls::steer,
                &NativeResetControls::pitch, &NativeResetControls::yaw, &NativeResetControls::roll,
                &NativeResetControls::dodgeForward, &NativeResetControls::dodgeStrafe}) {
            for (float value : {std::numeric_limits<float>::infinity(),
                    std::numeric_limits<float>::quiet_NaN(), -1.001f, 1.001f}) {
                World bad; bad.sample.controls.*field = value; bad.tick();
                check(bad.probe.status()["samples"].empty(), "Invalid control published");
            }
        }
        World missingController; missingController.scope.controller = 0; missingController.tick();
        check(missingController.reads == 0, "Missing human controller admitted");
        World bounded;
        // Worst float serialization magnitude and all populated fields, within FileBridge's 2 MiB cap.
        for (auto* body : {&bounded.sample.car, &bounded.sample.ball}) {
            body->location.fill(std::numeric_limits<float>::max());
            body->linearVelocity.fill(std::numeric_limits<float>::lowest());
            body->angularVelocity.fill(std::numeric_limits<float>::max());
            body->quaternionXyzw.fill(std::numeric_limits<float>::lowest());
            body->time = std::numeric_limits<float>::max();
        }
        for (std::size_t i = 0; i < NativeResetObservation::kMaxSamples + 5; ++i) bounded.tick();
        check(bounded.reads == NativeResetObservation::kMaxSamples, "Observation bound exceeded");
        const auto bytes = bounded.probe.status().dump().size();
        check(bytes < 2 * 1024 * 1024, "Diagnostic exceeds FileBridge limit");
        std::cout << "150 fully populated samples: " << bytes << " bytes\n";
        std::cout << "Native reset observation gates, fixed deadline and raw bounded samples passed\n";
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
