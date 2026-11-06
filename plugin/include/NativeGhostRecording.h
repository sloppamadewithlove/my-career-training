#pragma once

// Existing worker telemetry -> immutable frame input. This never chooses a
// recording, advances its clock, certifies a demonstration or writes game state.
#include "LocalBridge.h"
#include "NativeGhostRenderFrame.h"

namespace mct {

inline std::optional<NativeGhostRenderSample> nativeGhostSampleFromState(const Json& state) {
    const auto session = objectValue(state, "session");
    const auto telemetry = objectValue(state, "telemetry");
    const auto practice = objectValue(telemetry, "ghost_practice");
    const auto support = objectValue(telemetry, "ghost_practice_support");
    const auto provenance = objectValue(practice, "provenance");
    const auto pose = objectValue(practice, "pose");
    const auto actions = objectValue(pose, "actions");
    const auto lesson = stringValue(telemetry, "lesson_id");
    if (stringValue(session, "kind") != "training" || stringValue(session, "state") != "training" ||
        !boolValue(session, "worker_running") || stringValue(session, "id").empty() ||
        lesson.empty() || stringValue(practice, "lesson_id") != lesson ||
        !boolValue(support, "supported") || !boolValue(practice, "available") ||
        !boolValue(practice, "enabled") || !boolValue(practice, "visible") ||
        !boolValue(provenance, "compatibility") ||
        !practice.contains("player_input_applied") || practice["player_input_applied"] != false ||
        !telemetry.contains("ghost_practice_pending") || telemetry["ghost_practice_pending"] != false ||
        stringValue(practice, "status") == "capture_gap" ||
        objectValue(practice, "coach_actions") != actions) return {};
    for (const char* key : {"reference_capture", "capture"}) {
        const auto found = telemetry.find(key);
        if (found != telemetry.end() && !found->is_null() && *found != false &&
            !(found->is_object() && found->empty())) return {};
    }
    if (lesson == "flip-reset" && stringValue(provenance, "outcome") != "success") return {};

    NativeGhostRenderSample sample;
    const auto number = [](const Json& object, const char* key, double& output) {
        const auto found = object.find(key);
        if (found == object.end() || !found->is_number()) return false;
        output = found->get<double>();
        return std::isfinite(output);
    };
    const auto vector = [](const Json& object, const char* key, auto& output) {
        const auto found = object.find(key);
        if (found == object.end() || !found->is_array() || found->size() != output.size()) return false;
        for (std::size_t index = 0; index < output.size(); ++index) {
            if (!(*found)[index].is_number()) return false;
            const double value = (*found)[index].template get<double>();
            if (!std::isfinite(value) || std::abs(value) > 1000000) return false;
            output[index] = static_cast<float>(value);
        }
        return true;
    };
    double cursor = -1;
    std::array<float, 4> wxyz;
    std::array<float, 3> ball;
    if (!number(pose, "time", sample.recordedSeconds) || sample.recordedSeconds < 0 ||
        !number(practice, "cursor", cursor) || cursor != sample.recordedSeconds ||
        !vector(pose, "position", sample.car.position) || !vector(pose, "quaternion", wxyz) ||
        !vector(pose, "ball_position", ball)) return {};
    // recordings.euler_quaternion and interpolation use w,x,y,z. Native proxy
    // geometry uses x,y,z,w; converting exactly here avoids a silent roll.
    sample.car.orientation = {wxyz[1], wxyz[2], wxyz[3], wxyz[0]};
    if (!prepareNativeGhostProxy(sample.car)) return {};
    NativeDrawActions held;
    std::size_t axis = 0;
    for (const char* key : {"throttle", "steer", "pitch", "yaw", "roll"}) {
        double value;
        if (!number(actions, key, value) || value < -1 || value > 1) return {};
        held.axes[axis++] = static_cast<float>(value);
    }
    for (const char* key : {"jump", "boost", "handbrake"})
        if (!actions.contains(key) || !actions[key].is_boolean()) return {};
    held.jump = actions["jump"].get<bool>();
    held.boost = actions["boost"].get<bool>();
    held.handbrake = actions["handbrake"].get<bool>();
    sample.ballPosition = ball;
    sample.actions = held;
    return sample;
}

} // namespace mct
