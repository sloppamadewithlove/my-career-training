#include "NativeGhostProxy.h"

#include <algorithm>
#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>
#include <utility>
#include <vector>

using namespace mct;
static void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
static bool near(float a, float b) { return std::abs(a - b) < 0.001f; }

// A separating axis permits boundary contact, but excludes positive-area overlap.
static bool sideTrianglesOverlap(const NativeGhostProxyMesh& mesh,
        const std::array<std::uint8_t, 3>& a, const std::array<std::uint8_t, 3>& b) {
    for (const auto& triangle : {a, b})
        for (std::size_t edge = 0; edge < 3; ++edge) {
            const auto& from = mesh.vertices[triangle[edge]];
            const auto& to = mesh.vertices[triangle[(edge + 1) % 3]];
            const double nx = to[2] - from[2], nz = from[0] - to[0];
            double aMin = std::numeric_limits<double>::infinity(), aMax = -aMin;
            double bMin = aMin, bMax = aMax;
            for (std::size_t vertex = 0; vertex < 3; ++vertex) {
                const auto& av = mesh.vertices[a[vertex]];
                const auto& bv = mesh.vertices[b[vertex]];
                const double ap = nx * av[0] + nz * av[2], bp = nx * bv[0] + nz * bv[2];
                aMin = std::min(aMin, ap); aMax = std::max(aMax, ap);
                bMin = std::min(bMin, bp); bMax = std::max(bMax, bp);
            }
            if (aMax <= bMin + 0.000001 || bMax <= aMin + 0.000001) return false;
        }
    return true;
}

int main() {
    try {
        NativeGhostProxyPose pose;
        const auto identity = prepareNativeGhostProxy(pose);
        require(identity && identity->vertices == kNativeGhostProxyVertices &&
            identity->triangles == kNativeGhostProxyTriangles, "Identity changed local geometry");
        pose.position = {100, -200, 50};
        const auto translated = prepareNativeGhostProxy(pose);
        require(bool(translated), "Valid translation rejected");
        for (std::size_t vertex = 0; vertex < identity->vertices.size(); ++vertex)
            for (std::size_t axis = 0; axis < 3; ++axis)
                require(near(translated->vertices[vertex][axis],
                    identity->vertices[vertex][axis] + pose.position[axis]), "Translation changed shape");

        const float halfTurn = std::sqrt(0.5f);
        for (std::size_t axis = 0; axis < 3; ++axis) {
            pose = {};
            pose.orientation = {0, 0, 0, halfTurn};
            pose.orientation[axis] = halfTurn;
            const auto rotated = prepareNativeGhostProxy(pose);
            require(bool(rotated), "Quarter-turn rotation rejected");
            for (std::size_t vertex = 0; vertex < identity->vertices.size(); ++vertex) {
                const auto& local = identity->vertices[vertex];
                auto expected = local;
                const auto next = (axis + 1) % 3, last = (axis + 2) % 3;
                expected[next] = -local[last];
                expected[last] = local[next];
                for (std::size_t coordinate = 0; coordinate < 3; ++coordinate)
                    require(near(rotated->vertices[vertex][coordinate], expected[coordinate]),
                        "Quaternion rotation disagrees with local axes");
            }
            for (float& component : pose.orientation) component = -component;
            const auto negated = prepareNativeGhostProxy(pose);
            require(negated && negated->vertices == rotated->vertices, "Quaternion sign changed rotation");
        }

        for (float invalid : {std::numeric_limits<float>::quiet_NaN(),
                std::numeric_limits<float>::infinity(), -std::numeric_limits<float>::infinity()}) {
            for (std::size_t axis = 0; axis < 3; ++axis) {
                pose = {};
                pose.position[axis] = invalid;
                require(!prepareNativeGhostProxy(pose), "Nonfinite position admitted");
            }
            for (std::size_t component = 0; component < 4; ++component) {
                pose = {};
                pose.orientation[component] = invalid;
                require(!prepareNativeGhostProxy(pose), "Nonfinite orientation admitted");
            }
        }
        for (float invalid : {0.0f, 2.0f, std::numeric_limits<float>::max()}) {
            pose = {};
            pose.orientation = {0, 0, 0, invalid};
            require(!prepareNativeGhostProxy(pose), "Non-unit orientation admitted");
        }
        pose = {};
        pose.position = {1000000, -1000000, 1000000};
        require(bool(prepareNativeGhostProxy(pose)), "Bounded translation rejected");
        pose.position[0] = 1000001;
        require(!prepareNativeGhostProxy(pose), "Unbounded translation admitted");

        std::map<std::pair<int, int>, std::pair<int, int>> edges;
        std::array<std::vector<std::array<std::uint8_t, 3>>, 2> sides;
        std::array<double, 2> sideAreas{};
        double signedVolume = 0;
        for (const auto& triangle : identity->triangles) {
            for (auto index : triangle) require(index < identity->vertices.size(), "Invalid triangle index");
            const auto& a = identity->vertices[triangle[0]];
            const auto& b = identity->vertices[triangle[1]];
            const auto& c = identity->vertices[triangle[2]];
            const std::array<double, 3> ab{b[0]-a[0], b[1]-a[1], b[2]-a[2]};
            const std::array<double, 3> ac{c[0]-a[0], c[1]-a[1], c[2]-a[2]};
            const std::array<double, 3> normal{ab[1]*ac[2]-ab[2]*ac[1],
                ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0]};
            require(normal[0]*normal[0]+normal[1]*normal[1]+normal[2]*normal[2] > 0,
                "Degenerate filled triangle");
            if (a[1] == b[1] && a[1] == c[1]) {
                require(normal[0] == 0 && normal[2] == 0 && normal[1] * a[1] > 0,
                    "Side triangle points inward");
                const std::size_t side = a[1] < 0 ? 0 : 1;
                sides[side].push_back(triangle);
                sideAreas[side] += std::abs(normal[1]) / 2;
            }
            signedVolume += (a[0]*normal[0]+a[1]*normal[1]+a[2]*normal[2]) / 6;
            for (std::size_t edge = 0; edge < 3; ++edge) {
                const int from = triangle[edge], to = triangle[(edge + 1) % 3];
                auto& counts = edges[{std::min(from, to), std::max(from, to)}];
                ++counts.first;
                counts.second += from < to ? 1 : -1;
            }
        }
        for (const auto& edge : edges)
            require(edge.second.first == 2 && edge.second.second == 0,
                "Mesh is open or has inconsistent winding");
        require(identity->vertices.size() + identity->triangles.size() == edges.size() + 2 &&
            signedVolume > 0, "Mesh does not enclose an outward-wound solid");
        double polygonArea = 0;
        for (std::size_t vertex = 0; vertex < 8; ++vertex) {
            const auto& a = identity->vertices[vertex];
            const auto& b = identity->vertices[(vertex + 1) % 8];
            polygonArea += double(a[0]) * b[2] - double(a[2]) * b[0];
        }
        polygonArea = std::abs(polygonArea) / 2;
        require(polygonArea == 3555, "Unexpected silhouette area");
        require(sideTrianglesOverlap(*identity, {0, 4, 5}, {0, 5, 6}),
            "Overlap check missed the original concave-fan overlap");
        for (std::size_t side = 0; side < sides.size(); ++side) {
            require(sides[side].size() == 6 && sideAreas[side] == polygonArea,
                "Side triangles do not cover the silhouette area exactly");
            for (std::size_t a = 0; a < sides[side].size(); ++a)
                for (std::size_t b = a + 1; b < sides[side].size(); ++b)
                    require(!sideTrianglesOverlap(*identity, sides[side][a], sides[side][b]),
                        "Side triangles overlap in their interiors");
        }
        std::cout << "Native ghost proxy transform, finite input and closed geometry tests passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
