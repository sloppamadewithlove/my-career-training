#include "MyCareerTraining.h"
// Patch dependency: the independently reviewed recorded-worker adapter.
#include "NativeGhostRecording.h"
#include "bakkesmod/wrappers/GameObject/BallWrapper.h"
#include "bakkesmod/wrappers/GameObject/CarWrapper.h"
#include "bakkesmod/wrappers/PlayerControllerWrapper.h"
#include "bakkesmod/wrappers/GameEvent/ServerWrapper.h"
#include <windows.h>

mct::NativeDrawObservation MyCareerTraining::nativeGhostObservation(const mct::Json& state) const {
    mct::NativeDrawObservation live;
    if (!bridge_ || !nativeMovie_ || !ownedOfflineNow()) return live;
    std::string executable, core, build;
    if (!nativeMovie_->verifiedBuild(executable, core, build)) return live;
    const auto session = mct::objectValue(state, "session");
    if (mct::stringValue(session, "kind") != "training" ||
        mct::stringValue(session, "state") != "training" ||
        !mct::boolValue(session, "worker_running") || mct::boolValue(session, "busy")) return live;
    const auto nonce = mct::stringValue(state, "bridge_session");
    const auto source = mct::objectValue(mct::objectValue(state, "telemetry"), "native_ghost_source");
    const auto generation = bridge_->nativeGhostResetGeneration(mct::stringValue(session, "id"), nonce);
    if (generation.empty() || mct::stringValue(source, "reset_generation") != generation ||
        mct::stringValue(source, "bridge_session") != nonce || !mct::boolValue(source, "reset_observed")) return live;
    live.online = gameWrapper->IsInOnlineGame();
    live.replay = gameWrapper->IsInReplay();
    live.paused = gameWrapper->IsPaused();
    if (live.online || live.replay || live.paused || !gameWrapper->IsInGame()) return live;
    auto server = gameWrapper->GetCurrentGameState();
    auto car = gameWrapper->GetLocalCar();
    auto player = gameWrapper->GetPlayerController();
    if (!server || !car || !player || server.GetbMatchEnded()) return live;
    auto ball = server.GetBall();
    if (!ball) return live;
    live.identity.pid = GetCurrentProcessId();
    live.identity.created = processScope_.created;
    live.identity.nonce = nonce + ":" + generation;
    live.identity.event = server.memory_address;
    live.identity.car = car.memory_address;
    live.identity.ball = ball.memory_address;
    live.identity.round = server.GetRoundNum();
    live.ownedOffline = true;
    live.fresh = bridge_->fresh();
    live.buildVerified = true;
    live.workerTraining = true;
    live.carObserved = live.ballObserved = live.actionsObserved = true;
    live.gameSeconds = server.GetSecondsElapsed();
    const auto carPosition = car.GetLocation(), ballPosition = ball.GetLocation();
    live.carPosition = {carPosition.X, carPosition.Y, carPosition.Z};
    live.ballPosition = {ballPosition.X, ballPosition.Y, ballPosition.Z};
    const auto input = player.GetVehicleInput();
    live.actions.axes = {input.Throttle, input.Steer, input.Pitch, input.Yaw, input.Roll};
    live.actions.jump = input.Jump != 0;
    live.actions.boost = input.ActivateBoost != 0 || input.HoldingBoost != 0;
    live.actions.handbrake = input.Handbrake != 0;
    return live;
}

std::optional<mct::NativeDrawLease> MyCareerTraining::currentNativeGhostLease() {
    if (!bridge_) { clearNativeGhost(); return {}; }
    const auto state = bridge_->state();
    if (!mct::nativeGhostSampleFromState(state)) { nativeGhostPlayback_.clear(); return {}; }
    const auto live = nativeGhostObservation(state);
    // Sample expiry clocks after the fence and SDK reads, including any I/O delay.
    return nativeGhostPlayback_.current(state, live, mct::NativeGhostRenderer::now(), GetTickCount64());
}

void MyCareerTraining::updateNativeGhost(const mct::Json& state) {
    if (!nativeGhostRenderer_) return;
    const auto sample = mct::nativeGhostSampleFromState(state);
    const auto live = sample ? nativeGhostObservation(state) : mct::NativeDrawObservation{};
    const auto frame = nativeGhostPlayback_.update(state, live, sample,
        mct::NativeGhostRenderer::now(), GetTickCount64());
    if (!frame || !nativeGhostRenderer_->submit(frame)) clearNativeGhost();
}

void MyCareerTraining::clearNativeGhost() {
    nativeGhostPlayback_.clear();
    if (nativeGhostRenderer_) nativeGhostRenderer_->clear();
}
