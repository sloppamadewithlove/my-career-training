#include "NativeGhostRenderer.h"
#include "bakkesmod/wrappers/GameWrapper.h"
#include <iostream>

using namespace mct;
static void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }

int main() {
    try {
        const auto game = std::make_shared<GameWrapper>();
        std::optional<NativeDrawLease> lease;
        NativeGhostRenderer renderer(game, [&] { return lease; });
        CanvasWrapper canvas;
        const auto time = NativeGhostRenderer::now();
        NativeDrawIdentity id{42, 100, "synthetic-nonce-123456", 1, 2, 3, 1, 0};
        lease = NativeDrawLease{id, time - 1, time + 4};
        auto frame = std::make_shared<NativeGhostRenderFrame>();
        frame->lease = *lease;
        frame->observedAt = time;
        NativeGhostProxyPose pose;
        pose.position = {1000, 0, 0};
        frame->car = *prepareNativeGhostProxy(pose);
        for (auto& line : frame->ballLines) { line.start = {1000, 50, 10}; line.end = {1000, 60, 20}; }
        require(game->registrations == 0, "Construction registered an unavailable renderer");
        require(!renderer.submit({}) && game->registrations == 0, "Absent frame registered a callback");
        require(renderer.submit(frame) && game->registrations == 1, "Valid frame did not register");
        auto retained = game->callback;
        retained(canvas);
        require(canvas.calls->triangles == 28 && canvas.calls->lines == 72, "Car/ball not drawn together");
        require(renderer.submit(frame) && game->registrations == 1, "Update registered duplicate drawable");
        const auto hidden = [&] {
            const int previous = canvas.calls->triangles;
            retained(canvas);
            require(canvas.calls->triangles == previous, "Revoked frame remained visible");
        };
        lease.reset(); hidden();
        lease = frame->lease;
        retained(canvas);
        require(canvas.calls->triangles == 28, "Revoked frame reappeared without resubmission");
        for (bool* flag : {&game->online, &game->replay, &game->paused}) {
            require(renderer.submit(frame), "Could not resubmit current frame");
            *flag = true; hidden(); *flag = false;
        }
        require(renderer.submit(frame), "Could not resubmit before training loss");
        game->training = false; hidden(); game->training = true;
        require(renderer.submit(frame), "Could not resubmit before actor loss");
        game->server.ball.memory_address = 4; hidden(); game->server.ball.memory_address = 3;
        require(renderer.submit(frame), "Could not resubmit before car loss");
        game->car.memory_address = 4; hidden(); game->car.memory_address = 2;
        require(renderer.submit(frame), "Could not resubmit before event loss");
        game->server.memory_address = 4; hidden(); game->server.memory_address = 1;
        require(renderer.submit(frame), "Could not resubmit before epoch change");
        ++lease->identity.epoch; hidden(); lease = frame->lease;
        require(renderer.submit(frame), "Could not resubmit before lease renewal");
        lease->issued += .01; hidden(); lease = frame->lease;
        auto renewed = std::make_shared<NativeGhostRenderFrame>(*frame);
        lease->issued += .01;
        renewed->lease = *lease;
        require(renderer.submit(renewed), "Matching renewed frame/lease rejected");
        retained(canvas);
        lease = frame->lease;
        auto stale = std::make_shared<NativeGhostRenderFrame>(*frame);
        stale->observedAt = time - 0.11;
        require(!renderer.submit(stale), "Stale frame admitted");
        require(renderer.submit(frame), "Could not resubmit before explicit clear");
        renderer.clear(); hidden();
        require(renderer.submit(frame), "Could not resubmit before draw failure");
        canvas.calls->failLine = true;
        retained(canvas);
        require(canvas.calls->color.R == 1 && canvas.calls->color.A == 1, "Draw failure leaked Canvas color");
        canvas.calls->failLine = false;
        hidden();
        renderer.stop();
        require(game->unregistrations == 1 && !game->callback, "Stop failed to unregister");
        hidden();
        renderer.stop();
        require(game->unregistrations == 1 && !renderer.submit(frame), "Stopped renderer was revived");
        game->callback = [](CanvasWrapper) {};
        { NativeGhostRenderer unused(game, [&] { return lease; }); }
        require(game->unregistrations == 1 && bool(game->callback), "Unused renderer removed another drawable");
        std::cout << "Native ghost SDK-double scope revocation, clear, failure and callback cleanup passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
