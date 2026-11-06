#include "NativeGhostRenderer.h"
#include "NativeGhostProjection.h"
#include "bakkesmod/wrappers/GameWrapper.h"
#include "bakkesmod/wrappers/GameObject/CameraWrapper.h"
#include "bakkesmod/wrappers/GameObject/CarWrapper.h"
#include "bakkesmod/wrappers/GameObject/BallWrapper.h"
#include "bakkesmod/wrappers/GameEvent/ServerWrapper.h"
#include <chrono>

namespace mct {

struct NativeGhostRenderer::State {
    std::shared_ptr<GameWrapper> game;
    CurrentLease currentLease;
    std::shared_ptr<const NativeGhostRenderFrame> frame;

    bool current(double time) {
        if (!frame || !currentLease || !game || game->IsInOnlineGame() || game->IsInReplay() ||
            game->IsPaused() || !game->IsInCustomTraining()) return false;
        const auto lease = currentLease();
        if (!lease || !nativeGhostRenderFrameCurrent(*frame, *lease, time)) return false;
        auto server = game->GetCurrentGameState();
        auto car = game->GetLocalCar();
        if (server.IsNull() || car.IsNull()) return false;
        auto ball = server.GetBall();
        return !ball.IsNull() && server.memory_address == lease->identity.event &&
            car.memory_address == lease->identity.car && ball.memory_address == lease->identity.ball;
    }

    void draw(CanvasWrapper canvas) {
        try {
            if (!current(NativeGhostRenderer::now())) { frame.reset(); return; }
            auto camera = game->GetCamera();
            if (camera.IsNull()) return;
            const auto location = camera.GetLocation(), forward = RotatorToVector(camera.GetRotation());
            const auto size = canvas.GetSize();
            const auto screen = projectNativeGhostFrame(*frame,
                {location.X, location.Y, location.Z}, {forward.X, forward.Y, forward.Z}, size.X, size.Y,
                [&](const auto& world) {
                    const auto p = canvas.ProjectF(Vector{world[0], world[1], world[2]});
                    return NativeGhostScreenPoint{p.X, p.Y};
                });
            if (!screen) return;
            const auto pixel = [](NativeGhostScreenPoint p) { return Vector2F{p.x, p.y}; };
            struct RestoreColor {
                CanvasWrapper& canvas;
                LinearColor value;
                ~RestoreColor() { try { canvas.SetColor(value); } catch (...) {} }
            } restore{canvas, canvas.GetColor()};
            const LinearColor carColor{0.15f, 0.75f, 1.0f, 0.12f};
            for (const auto& triangle : screen->triangles)
                canvas.FillTriangle(pixel(screen->car[triangle[0]]), pixel(screen->car[triangle[1]]),
                    pixel(screen->car[triangle[2]]), carColor);
            canvas.SetColor(LinearColor{0.5f, 0.9f, 1.0f, 0.35f});
            for (const auto& line : screen->ball) canvas.DrawLine(pixel(line[0]), pixel(line[1]), 1.0f);
        } catch (...) { frame.reset(); }
    }
};

NativeGhostRenderer::NativeGhostRenderer(std::shared_ptr<GameWrapper> game, CurrentLease currentLease)
    : state_(std::make_shared<State>()) {
    state_->game = std::move(game);
    state_->currentLease = std::move(currentLease);
}

NativeGhostRenderer::~NativeGhostRenderer() { stop(); }

double NativeGhostRenderer::now() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

bool NativeGhostRenderer::submit(std::shared_ptr<const NativeGhostRenderFrame> frame) {
    if (!state_) return false;
    state_->frame = std::move(frame);
    try {
        if (!state_->current(now())) { clear(); return false; }
        if (!registered_) {
            const std::weak_ptr<State> weak = state_;
            state_->game->RegisterDrawable([weak](CanvasWrapper canvas) {
                if (const auto state = weak.lock()) state->draw(canvas);
            });
            registered_ = true;
        }
        return true;
    } catch (...) { clear(); return false; }
}

void NativeGhostRenderer::clear() { if (state_) state_->frame.reset(); }

void NativeGhostRenderer::stop() {
    if (!state_) return;
    auto game = state_->game;
    // Revoke first: even a retained callback has only an expired weak reference.
    state_.reset();
    if (registered_) {
        registered_ = false;
        // SDK removes all drawables for this plugin; this is its sole Canvas owner.
        try { game->UnregisterDrawables(); } catch (...) {}
    }
}

} // namespace mct
