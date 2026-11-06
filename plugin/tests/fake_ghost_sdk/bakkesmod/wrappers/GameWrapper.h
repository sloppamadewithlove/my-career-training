#pragma once

// Test double for the renderer's SDK boundary; the DLL separately builds against
// the real pinned SDK. These counters prove our lifecycle, not SDK internals.
#include <cstdint>
#include <array>
#include <functional>
#include <memory>
#include <stdexcept>

struct Vector { float X, Y, Z; };
struct Vector2 { int X, Y; };
struct Vector2F { float X, Y; };
struct Rotator {};
inline Vector RotatorToVector(Rotator) { return {1, 0, 0}; }
struct LinearColor { float R, G, B, A; };
using GhostColorBytes = std::array<std::uint8_t, 4>;
inline GhostColorBytes ghostColorBytes(LinearColor c) {
    return {static_cast<std::uint8_t>(static_cast<int>(c.R)),
        static_cast<std::uint8_t>(static_cast<int>(c.G)),
        static_cast<std::uint8_t>(static_cast<int>(c.B)),
        static_cast<std::uint8_t>(static_cast<int>(c.A))};
}
struct GhostCanvasCalls {
    int triangles = 0, lines = 0;
    bool failLine = false;
    GhostColorBytes color{17, 31, 47, 223}, triangleColor{}, lineColor{};
};
class CanvasWrapper {
public:
    std::shared_ptr<GhostCanvasCalls> calls = std::make_shared<GhostCanvasCalls>();
    Vector2 GetSize() { return {1920, 1080}; }
    Vector2F ProjectF(Vector p) { return {960 + p.Y, 540 + p.Z}; }
    LinearColor GetColor() {
        return {float(calls->color[0]), float(calls->color[1]), float(calls->color[2]), float(calls->color[3])};
    }
    void SetColor(LinearColor c) { calls->color = ghostColorBytes(c); }
    void FillTriangle(Vector2F, Vector2F, Vector2F, LinearColor c) {
        ++calls->triangles;
        calls->triangleColor = ghostColorBytes(c);
    }
    void DrawLine(Vector2F, Vector2F, float) {
        if (calls->failLine) throw std::runtime_error("Synthetic draw failure");
        ++calls->lines;
        calls->lineColor = calls->color;
    }
};
class BallWrapper {
public:
    std::uintptr_t memory_address = 3;
    bool IsNull() { return memory_address == 0; }
};
class CarWrapper {
public:
    std::uintptr_t memory_address = 2;
    bool IsNull() { return memory_address == 0; }
};
class ServerWrapper {
public:
    std::uintptr_t memory_address = 1;
    BallWrapper ball;
    bool IsNull() { return memory_address == 0; }
    BallWrapper GetBall() { return ball; }
};
class CameraWrapper {
public:
    bool IsNull() { return false; }
    Vector GetLocation() { return {0, 0, 0}; }
    Rotator GetRotation() { return {}; }
};
class GameWrapper {
public:
    bool online = false, replay = false, paused = false, training = true, inGame = false;
    int registrations = 0, unregistrations = 0;
    CarWrapper car;
    ServerWrapper server;
    std::function<void(CanvasWrapper)> callback;
    bool IsInOnlineGame() { return online; }
    bool IsInReplay() { return replay; }
    bool IsPaused() { return paused; }
    bool IsInCustomTraining() { return training; }
    bool IsInGame() { return inGame; }
    ServerWrapper GetCurrentGameState() { return server; }
    CarWrapper GetLocalCar() { return car; }
    CameraWrapper GetCamera() { return {}; }
    void RegisterDrawable(std::function<void(CanvasWrapper)> draw) { ++registrations; callback = std::move(draw); }
    void UnregisterDrawables() { ++unregistrations; callback = {}; }
};
