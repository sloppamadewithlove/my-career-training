#pragma once

// Pure diagnostic frame preparation. No SDK, callback registration, replay,
// game mutation or teaching-availability authority lives here.
#include <array>
#include <cmath>
#include <cstdint>
#include <memory>
#include <string>

namespace mct {

struct NativeDrawIdentity {
    std::uint32_t pid = 0;
    double created = 0;
    std::string nonce;
    std::uintptr_t event = 0, car = 0, ball = 0;
    std::uint64_t epoch = 0;
    int round = -1;
};

struct NativeDrawLease {
    NativeDrawIdentity identity;
    double issued = 0, expires = 0;
};

struct NativeDrawActions {
    std::array<float, 5> axes{}; // throttle, steer, pitch, yaw, roll
    bool jump = false, boost = false, handbrake = false;
};

struct NativeDrawObservation {
    NativeDrawIdentity identity;
    bool ownedOffline = false, fresh = false, buildVerified = false;
    bool customTraining = false, online = false, replay = false, paused = false;
    // Explicit attestation of this owned active worker lesson, not just IsInGame.
    bool workerTraining = false;
    bool carObserved = false, ballObserved = false, actionsObserved = false;
    double observedAt = 0, gameSeconds = 0;
    std::array<float, 3> carPosition{}, ballPosition{};
    NativeDrawActions actions;
};

struct NativeDrawMarkerLine {
    std::array<float, 3> start{}, end{};
    bool ball = false;
};

struct NativeDrawDiagnosticFrame {
    static constexpr const char* kLabel = "Native renderer diagnostic: live positions/inputs";
    NativeDrawLease lease;
    double observedAt = 0, gameSeconds = 0;
    std::array<NativeDrawMarkerLine, 6> lines{};
    NativeDrawActions actions;
};

inline constexpr double kNativeDrawMaxAge = 0.1;
inline constexpr double kNativeDrawMaxLease = 5.0;

inline bool nativeDrawIdentityValid(const NativeDrawIdentity& value) {
    return value.pid != 0 && std::isfinite(value.created) && value.created > 0 &&
        value.nonce.size() >= 16 && value.nonce.size() <= 128 && value.event != 0 &&
        value.car != 0 && value.ball != 0 && value.epoch != 0 && value.round >= 0;
}

inline bool sameNativeDrawIdentity(const NativeDrawIdentity& a, const NativeDrawIdentity& b) {
    return a.pid == b.pid && a.created == b.created && a.nonce == b.nonce &&
        a.event == b.event && a.car == b.car && a.ball == b.ball &&
        a.epoch == b.epoch && a.round == b.round;
}

inline bool nativeDrawLeaseCurrent(const NativeDrawLease& lease, double now) {
    return nativeDrawIdentityValid(lease.identity) && std::isfinite(now) &&
        std::isfinite(lease.issued) && lease.issued >= 0 && std::isfinite(lease.expires) &&
        lease.expires > lease.issued && lease.expires - lease.issued <= kNativeDrawMaxLease &&
        now >= lease.issued && now < lease.expires;
}

// A future draw consumer must recheck age and identity, even without new ticks.
inline bool nativeDrawFrameCurrent(const NativeDrawDiagnosticFrame& frame,
                                  const NativeDrawLease& live, double now) {
    return nativeDrawLeaseCurrent(live, now) &&
        sameNativeDrawIdentity(frame.lease.identity, live.identity) &&
        frame.lease.issued == live.issued && frame.lease.expires == live.expires &&
        std::isfinite(frame.observedAt) && frame.observedAt >= live.issued &&
        now >= frame.observedAt && now - frame.observedAt <= kNativeDrawMaxAge;
}

inline std::shared_ptr<const NativeDrawDiagnosticFrame> prepareNativeDrawDiagnostic(
        const NativeDrawObservation& observation, const NativeDrawLease& lease, double now) {
    if (!nativeDrawLeaseCurrent(lease, now) ||
        !sameNativeDrawIdentity(observation.identity, lease.identity) ||
        !observation.ownedOffline || !observation.fresh || !observation.buildVerified ||
        (!observation.customTraining && !observation.workerTraining) ||
        observation.online || observation.replay || observation.paused ||
        !observation.carObserved || !observation.ballObserved || !observation.actionsObserved ||
        !std::isfinite(observation.gameSeconds) || observation.gameSeconds < 0) return {};
    for (const auto& position : {observation.carPosition, observation.ballPosition})
        for (float coordinate : position)
            if (!std::isfinite(coordinate) || std::abs(coordinate) > 1000000.0f) return {};
    for (float action : observation.actions.axes)
        if (!std::isfinite(action) || action < -1 || action > 1) return {};

    auto frame = std::make_shared<NativeDrawDiagnosticFrame>();
    frame->lease = lease;
    frame->observedAt = observation.observedAt;
    frame->gameSeconds = observation.gameSeconds;
    frame->actions = observation.actions;
    if (!nativeDrawFrameCurrent(*frame, lease, now)) return {};
    // Position crosses are diagnostic markers, not an oriented demonstration car.
    for (std::size_t actor = 0; actor < 2; ++actor) {
        const auto& position = actor == 0 ? observation.carPosition : observation.ballPosition;
        for (std::size_t axis = 0; axis < 3; ++axis) {
            auto& line = frame->lines[actor * 3 + axis];
            line.start = line.end = position;
            line.start[axis] -= 20;
            line.end[axis] += 20;
            line.ball = actor == 1;
        }
    }
    return frame;
}

} // namespace mct
