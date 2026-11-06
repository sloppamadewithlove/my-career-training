#pragma once

// Pure recorded-frame preparation only. No renderer, SDK conversion, game actor,
// recording certification or teaching-availability authority is installed here.
#include "NativeGhostProxy.h"
#include "NativeTrainingDrawProbe.h"

#include <optional>

namespace mct {

struct NativeGhostRenderSample {
    // One already interpolated recording timestamp; actions remain sample-held.
    // The producer must convert recording quaternions to the proxy's x,y,z,w order.
    double recordedSeconds = -1;
    bool captureGap = false;
    NativeGhostProxyPose car;
    std::optional<std::array<float, 3>> ballPosition;
    std::optional<NativeDrawActions> actions;
};

struct NativeGhostRenderFrame {
    static constexpr const char* kLabel = "Recorded ghost rendering candidate: unverified";
    NativeDrawLease lease;
    double observedAt = 0, gameSeconds = 0, recordedSeconds = 0;
    NativeGhostProxyMesh car;
    std::array<NativeDrawMarkerLine, 72> ballLines{};
    NativeDrawActions actions;
};

// Draw consumers must check this even without a new tick. Scope loss must revoke
// the live lease; a fixed-start retry must change its epoch before drawing again.
inline bool nativeGhostRenderFrameCurrent(const NativeGhostRenderFrame& frame,
        const NativeDrawLease& live, double now) {
    NativeDrawDiagnosticFrame clock;
    clock.lease = frame.lease;
    clock.observedAt = frame.observedAt;
    return nativeDrawFrameCurrent(clock, live, now);
}

inline std::shared_ptr<const NativeGhostRenderFrame> prepareNativeGhostRenderFrame(
        const NativeDrawObservation& live, const NativeDrawLease& lease,
        const NativeGhostRenderSample& sample, double now) {
    const auto diagnostic = prepareNativeDrawDiagnostic(live, lease, now);
    if (!diagnostic || sample.captureGap || !std::isfinite(sample.recordedSeconds) ||
        sample.recordedSeconds < 0 || !sample.ballPosition || !sample.actions) return {};
    const auto car = prepareNativeGhostProxy(sample.car);
    if (!car) return {};
    for (float coordinate : *sample.ballPosition)
        if (!std::isfinite(coordinate) || std::abs(coordinate) > 1000000.0f) return {};
    for (float action : sample.actions->axes)
        if (!std::isfinite(action) || action < -1 || action > 1) return {};

    auto frame = std::make_shared<NativeGhostRenderFrame>();
    frame->lease = diagnostic->lease;
    frame->observedAt = diagnostic->observedAt;
    frame->gameSeconds = diagnostic->gameSeconds;
    frame->recordedSeconds = sample.recordedSeconds;
    frame->car = *car;
    frame->actions = *sample.actions;
    // Three self-authored circular outlines depict a non-contact demonstration
    // ball. This diagnostic radius is not a claim about the game's collision mesh.
    constexpr double radius = 90, tau = 6.2831853071795864769;
    for (std::size_t plane = 0; plane < 3; ++plane)
        for (std::size_t edge = 0; edge < 24; ++edge) {
            auto& line = frame->ballLines[plane * 24 + edge];
            line.start = line.end = *sample.ballPosition;
            line.ball = true;
            const auto a = (plane + 1) % 3, b = (plane + 2) % 3;
            line.start[a] += static_cast<float>(radius * std::cos(tau * edge / 24));
            line.start[b] += static_cast<float>(radius * std::sin(tau * edge / 24));
            line.end[a] += static_cast<float>(radius * std::cos(tau * ((edge + 1) % 24) / 24));
            line.end[b] += static_cast<float>(radius * std::sin(tau * ((edge + 1) % 24) / 24));
        }
    return frame;
}

} // namespace mct
