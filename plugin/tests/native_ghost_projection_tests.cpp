#include "NativeGhostProjection.h"
#include <iostream>
#include <limits>
#include <stdexcept>

using namespace mct;

static void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

int main() {
    try {
        NativeGhostRenderFrame frame;
        NativeGhostProxyPose pose;
        pose.position = {1000, 0, 0};
        frame.car = *prepareNativeGhostProxy(pose);
        for (auto& line : frame.ballLines) { line.start = {1000, 50, 10}; line.end = {1000, 60, 20}; }
        int projected = 0;
        const auto project = [&](const auto& world) {
            ++projected;
            return NativeGhostScreenPoint{world[1] + 500, world[2] + 300};
        };
        const std::array<float, 3> camera{}, forward{1, 0, 0};
        const auto screen = projectNativeGhostFrame(frame, camera, forward, 1000, 600, project);
        require(screen.has_value(), "Valid synchronized pair not projected");
        require(projected == 16 + 144, "Car and ball did not use the same projection batch");
        require(screen->car[0].x == 468 && screen->ball[0][0].x == 550,
            "Projection changed car or ball coordinates");
        double previous = std::numeric_limits<double>::infinity();
        for (const auto& triangle : screen->triangles) {
            double depth = 0;
            for (auto index : triangle) depth += frame.car.vertices[index][0];
            require(depth <= previous, "Translucent surfaces not ordered far to near");
            previous = depth;
        }
        auto malformed = frame;
        malformed.car.triangles[0][0] = 255;
        require(!projectNativeGhostFrame(malformed, camera, forward, 1000, 600, project),
            "Invalid index admitted");
        for (float x : {-1000.f, 0.f, 10.f, std::numeric_limits<float>::infinity(),
                std::numeric_limits<float>::quiet_NaN()}) {
            malformed = frame;
            malformed.ballLines.back().end[0] = x;
            require(!projectNativeGhostFrame(malformed, camera, forward, 1000, 600, project),
                "Invalid or behind-camera ball drew a partial pair");
            malformed = frame;
            malformed.car.vertices[0][0] = x;
            require(!projectNativeGhostFrame(malformed, camera, forward, 1000, 600, project),
                "Invalid or behind-camera car drew a partial pair");
        }
        require(!projectNativeGhostFrame(frame, camera, {0, 0, 0}, 1000, 600, project),
            "Invalid camera direction admitted");
        require(!projectNativeGhostFrame(frame, camera, forward, 0, 600, project),
            "Missing viewport admitted");
        require(!projectNativeGhostFrame(frame, camera, forward, 1000, 600,
            [](const auto&) { return NativeGhostScreenPoint{-1, 100}; }), "Offscreen point admitted");
        require(!projectNativeGhostFrame(frame, camera, forward, 1000, 600,
            [](const auto&) { return NativeGhostScreenPoint{std::numeric_limits<float>::quiet_NaN(), 100}; }),
            "Nonfinite SDK projection admitted");
        std::cout << "Native ghost paired projection, near-plane, finite input and painter ordering passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
