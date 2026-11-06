#pragma once

// Test double for the renderer's SDK boundary; the DLL separately builds against
// the real pinned SDK. These counters prove our lifecycle, not SDK internals.
#include <cstdint>
#include <functional>
#include <memory>
#include <stdexcept>

struct Vector { float X, Y, Z; };
struct Vector2 { int X, Y; };
struct Vector2F { float X, Y; };
struct Rotator {};
inline Vector RotatorToVector(Rotator) { return {1, 0, 0}; }
struct LinearColor { float R, G, B, A; };
struct GhostCanvasCalls {
    int triangles = 0, lines = 0;
    bool failLine = false;
    LinearColor color{1, 1, 1, 1};
};
class CanvasWrapper {
public:
    std::shared_ptr<GhostCanvasCalls> calls = std::make_shared<GhostCanvasCalls>();
    Vector2 GetSize() { return {1920, 1080}; }
    Vector2F ProjectF(Vector p) { return {960 + p.Y, 540 + p.Z}; }
    LinearColor GetColor() { return calls->color; }
    void SetColor(LinearColor c) { calls->color = c; }
    void FillTriangle(Vector2F, Vector2F, Vector2F, LinearColor) { ++calls->triangles; }
    void DrawLine(Vector2F, Vector2F, float) {
        if (calls->failLine) throw std::runtime_error("Synthetic draw failure");
        ++calls->lines;
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
    bool online = false, replay = false, paused = false, training = true;
    int registrations = 0, unregistrations = 0;
    CarWrapper car;
    ServerWrapper server;
    std::function<void(CanvasWrapper)> callback;
    bool IsInOnlineGame() { return online; }
    bool IsInReplay() { return replay; }
    bool IsPaused() { return paused; }
    bool IsInCustomTraining() { return training; }
    ServerWrapper GetCurrentGameState() { return server; }
    CarWrapper GetLocalCar() { return car; }
    CameraWrapper GetCamera() { return {}; }
    void RegisterDrawable(std::function<void(CanvasWrapper)> draw) { ++registrations; callback = std::move(draw); }
    void UnregisterDrawables() { ++unregistrations; callback = {}; }
};
