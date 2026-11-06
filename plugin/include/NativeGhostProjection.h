#pragma once

#include "NativeGhostRenderFrame.h"
#include <algorithm>

namespace mct {

struct NativeGhostScreenPoint { float x = 0, y = 0; };
struct NativeGhostScreenFrame {
    std::array<NativeGhostScreenPoint, 16> car;
    std::array<std::array<std::uint8_t, 3>, 28> triangles;
    std::array<std::array<NativeGhostScreenPoint, 2>, 72> ball;
};

// Project the pair before drawing either actor. A near-plane intersection hides
// this frame instead of producing inverted triangles or a disconnected ball.
template<class Project>
std::optional<NativeGhostScreenFrame> projectNativeGhostFrame(
        const NativeGhostRenderFrame& frame, const std::array<float, 3>& camera,
        const std::array<float, 3>& forward, int width, int height, Project project) {
    if (width <= 0 || height <= 0 || width > 32768 || height > 32768) return {};
    double forwardNorm = 0;
    for (std::size_t axis = 0; axis < 3; ++axis) {
        if (!std::isfinite(camera[axis]) || !std::isfinite(forward[axis])) return {};
        forwardNorm += double(forward[axis]) * forward[axis];
    }
    if (std::abs(forwardNorm - 1) > 0.001) return {};
    const auto point = [&](const std::array<float, 3>& world) -> std::optional<NativeGhostScreenPoint> {
        double depth = 0;
        for (std::size_t axis = 0; axis < 3; ++axis) {
            if (!std::isfinite(world[axis]) || std::abs(world[axis]) > 1000000) return {};
            depth += (double(world[axis]) - camera[axis]) * forward[axis];
        }
        if (depth <= 10) return {};
        const auto screen = project(world);
        if (!std::isfinite(screen.x) || !std::isfinite(screen.y) ||
            screen.x < 0 || screen.y < 0 || screen.x > width || screen.y > height) return {};
        return screen;
    };
    NativeGhostScreenFrame out;
    for (std::size_t i = 0; i < frame.car.vertices.size(); ++i) {
        const auto value = point(frame.car.vertices[i]);
        if (!value) return {};
        out.car[i] = *value;
    }
    out.triangles = frame.car.triangles;
    for (const auto& triangle : out.triangles)
        for (auto index : triangle)
            if (index >= out.car.size()) return {};
    // Painter ordering for the translucent proxy. Canvas has no world depth test.
    const auto depth = [&](const auto& triangle) {
        double value = 0;
        for (auto index : triangle)
            for (std::size_t axis = 0; axis < 3; ++axis)
                value += (double(frame.car.vertices[index][axis]) - camera[axis]) * forward[axis];
        return value;
    };
    std::stable_sort(out.triangles.begin(), out.triangles.end(),
        [&](const auto& a, const auto& b) { return depth(a) > depth(b); });
    for (std::size_t i = 0; i < frame.ballLines.size(); ++i) {
        const auto start = point(frame.ballLines[i].start), end = point(frame.ballLines[i].end);
        if (!start || !end) return {};
        out.ball[i] = {*start, *end};
    }
    return out;
}

} // namespace mct
