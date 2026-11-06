#include "NativeGhostRenderFrame.h"

#include <iostream>
#include <limits>
#include <stdexcept>
#include <type_traits>

using namespace mct;
static void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
static bool near(float a, float b) { return std::abs(a - b) < 0.001f; }

int main() {
    try {
        NativeDrawLease lease{{42, 100, "synthetic-owned-nonce", 10, 20, 30, 1, 0}, 10, 15};
        NativeDrawObservation live;
        live.identity = lease.identity;
        live.ownedOffline = live.fresh = live.buildVerified = live.customTraining = true;
        live.carObserved = live.ballObserved = live.actionsObserved = true;
        live.observedAt = 11;
        live.gameSeconds = 50;
        live.carPosition = {1000, 2000, 17};
        live.ballPosition = {3000, 4000, 93};

        // Synthetic geometry/transport fixture, never an actual teaching trace.
        NativeGhostRenderSample sample;
        sample.recordedSeconds = 1.25;
        sample.car.position = {100, 200, 500};
        sample.car.orientation = {1, 0, 0, 0};
        sample.ballPosition = std::array<float, 3>{120, 220, 600};
        sample.actions = NativeDrawActions{{1, -.5f, .25f, 0, 1}, true, true, false};
        auto frame = prepareNativeGhostRenderFrame(live, lease, sample, 11.01);
        static_assert(std::is_const_v<std::remove_reference_t<decltype(*frame)>>,
            "Render consumers must receive an immutable frame");
        require(frame && frame->recordedSeconds == 1.25 && frame->gameSeconds == 50,
            "Recording and live-clock timestamps were conflated");
        const auto& vertex = frame->car.vertices[4];
        require(near(vertex[0], 105) && near(vertex[1], 232) && near(vertex[2], 458),
            "Upside-down car geometry lost recorded orientation or translation");
        require(frame->actions.jump && frame->actions.boost && frame->actions.axes[1] == -.5f,
            "Held recording actions were replaced with live controls");
        require(frame->ballLines[0].start == std::array<float, 3>{120, 310, 600},
            "Demonstration ball used the real ball position or the car transform");
        for (std::size_t plane = 0; plane < 3; ++plane)
            for (std::size_t edge = 0; edge < 24; ++edge) {
                const auto& line = frame->ballLines[plane * 24 + edge];
                const auto& next = frame->ballLines[plane * 24 + (edge + 1) % 24];
                require(line.ball && line.end == next.start, "Ball outline is not a closed ring");
                for (const auto& point : {line.start, line.end}) {
                    double distanceSquared = 0;
                    for (std::size_t axis = 0; axis < 3; ++axis) {
                        const double delta = point[axis] - (*sample.ballPosition)[axis];
                        distanceSquared += delta * delta;
                    }
                    require(std::abs(distanceSquared - 8100) < .1, "Ball outline changed radius");
                }
            }
        sample.car.position = {0, 0, 0};
        sample.ballPosition->fill(0);
        sample.actions->jump = false;
        require(near(frame->car.vertices[4][2], 458) && frame->actions.jump &&
            frame->ballLines[0].start[2] == 600, "Published frame aliases mutable recording data");

        require(nativeGhostRenderFrameCurrent(*frame, lease, 11.01), "Fresh frame rejected");
        for (double now : {10.99, 11.11, 15.0, std::numeric_limits<double>::quiet_NaN()})
            require(!nativeGhostRenderFrameCurrent(*frame, lease, now), "Stale/expired frame remained visible");
        for (int identityChange = 0; identityChange < 4; ++identityChange) {
            auto changed = lease;
            if (identityChange == 0) ++changed.identity.epoch;
            if (identityChange == 1) ++changed.identity.round;
            if (identityChange == 2) ++changed.identity.car;
            if (identityChange == 3) ++changed.identity.ball;
            require(!nativeGhostRenderFrameCurrent(*frame, changed, 11.01),
                "Cached ghost crossed a reset, round or actor identity");
        }
        auto renewed = lease;
        renewed.issued = 10.5;
        require(!nativeGhostRenderFrameCurrent(*frame, renewed, 11.01), "Old frame survived a new lease");
        for (int failure = 0; failure < 9; ++failure) {
            auto bad = sample;
            if (failure == 0) bad.captureGap = true;
            if (failure == 1) bad.ballPosition.reset();
            if (failure == 2) bad.actions.reset();
            if (failure == 3) bad.recordedSeconds = -1;
            if (failure == 4) bad.recordedSeconds = std::numeric_limits<double>::quiet_NaN();
            if (failure == 5) (*bad.ballPosition)[0] = std::numeric_limits<float>::infinity();
            if (failure == 6) (*bad.ballPosition)[0] = 1000001;
            if (failure == 7) bad.actions->axes[0] = 1.01f;
            if (failure == 8) bad.car.orientation.fill(0);
            require(!prepareNativeGhostRenderFrame(live, lease, bad, 11.01),
                "Incomplete, gapped or malformed recording produced a frame");
        }
        live.paused = true;
        require(!prepareNativeGhostRenderFrame(live, lease, sample, 11.01), "Paused scope produced a frame");
        live.paused = false;
        live.online = true;
        require(!prepareNativeGhostRenderFrame(live, lease, sample, 11.01), "Online scope produced a frame");
        require(!prepareNativeGhostRenderFrame({}, {}, {}, 0), "Unknown/default scope produced a frame");
        std::cout << "Native ghost render frame coherence, geometry, immutability and expiry tests passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
