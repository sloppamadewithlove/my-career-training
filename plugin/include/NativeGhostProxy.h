#pragma once

// Self-authored diagnostic geometry only: no renderer, game model or visibility authority.
#include <array>
#include <cmath>
#include <cstdint>
#include <optional>

namespace mct {

struct NativeGhostProxyPose {
    std::array<float, 3> position{};
    // Local x forward, y left, z up; unit quaternion in x, y, z, w order.
    // This is a mathematical convention, not an SDK rotation conversion.
    std::array<float, 4> orientation{0, 0, 0, 1};
};

struct NativeGhostProxyMesh {
    std::array<std::array<float, 3>, 16> vertices{};
    std::array<std::array<std::uint8_t, 3>, 28> triangles{};
};

// Arbitrary diagnostic dimensions, with the origin at the lower body center.
inline constexpr std::array<std::array<float, 3>, 16> kNativeGhostProxyVertices{{
    {-60, -32, 0}, {60, -32, 0}, {60, -32, 20}, {25, -32, 20},
    {5, -32, 42}, {-30, -32, 42}, {-45, -32, 20}, {-60, -32, 20},
    {-60, 32, 0}, {60, 32, 0}, {60, 32, 20}, {25, 32, 20},
    {5, 32, 42}, {-30, 32, 42}, {-45, 32, 20}, {-60, 32, 20}
}};

// Closed, consistently outward-wound surfaces, suitable for filled triangle projection.
inline constexpr std::array<std::array<std::uint8_t, 3>, 28> kNativeGhostProxyTriangles{{
    {0, 1, 2}, {0, 2, 3}, {0, 3, 4}, {0, 4, 5}, {0, 5, 6}, {0, 6, 7},
    {8, 10, 9}, {8, 11, 10}, {8, 12, 11}, {8, 13, 12}, {8, 14, 13}, {8, 15, 14},
    {0, 8, 9}, {0, 9, 1}, {1, 9, 10}, {1, 10, 2},
    {2, 10, 11}, {2, 11, 3}, {3, 11, 12}, {3, 12, 4},
    {4, 12, 13}, {4, 13, 5}, {5, 13, 14}, {5, 14, 6},
    {6, 14, 15}, {6, 15, 7}, {7, 15, 8}, {7, 8, 0}
}};

inline std::optional<NativeGhostProxyMesh> prepareNativeGhostProxy(const NativeGhostProxyPose& pose) {
    for (float coordinate : pose.position)
        if (!std::isfinite(coordinate) || std::abs(coordinate) > 1000000.0f) return {};
    double normSquared = 0;
    for (float component : pose.orientation) {
        if (!std::isfinite(component)) return {};
        normSquared += double(component) * component;
    }
    if (std::abs(normSquared - 1.0) > 0.0001) return {};
    const double inverseNorm = 1.0 / std::sqrt(normSquared);
    const double x = pose.orientation[0] * inverseNorm, y = pose.orientation[1] * inverseNorm;
    const double z = pose.orientation[2] * inverseNorm, w = pose.orientation[3] * inverseNorm;
    const double rotation[3][3] = {
        {1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)},
        {2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)},
        {2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)}
    };
    NativeGhostProxyMesh mesh;
    mesh.triangles = kNativeGhostProxyTriangles;
    for (std::size_t vertex = 0; vertex < mesh.vertices.size(); ++vertex)
        for (std::size_t axis = 0; axis < 3; ++axis) {
            double coordinate = pose.position[axis];
            for (std::size_t local = 0; local < 3; ++local)
                coordinate += rotation[axis][local] * kNativeGhostProxyVertices[vertex][local];
            mesh.vertices[vertex][axis] = static_cast<float>(coordinate);
        }
    return mesh;
}

} // namespace mct
