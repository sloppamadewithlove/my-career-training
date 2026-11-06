#include "NativeTrainingDrawProbe.h"

#include <iostream>
#include <limits>
#include <stdexcept>
#include <type_traits>

using namespace mct;
static void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }

int main() {
    try {
        NativeDrawLease lease{{42, 100, "synthetic-owned-nonce", 10, 20, 30, 1, 0}, 10, 15};
        NativeDrawObservation observed;
        observed.identity = lease.identity;
        observed.ownedOffline = observed.fresh = observed.buildVerified = observed.customTraining = true;
        observed.carObserved = observed.ballObserved = observed.actionsObserved = true;
        observed.observedAt = 11;
        observed.gameSeconds = 20;
        observed.carPosition = {100, 200, 30};
        observed.ballPosition = {300, 400, 100};
        observed.actions.axes = {1, -0.5f, 0, 0.25f, 0};
        observed.actions.jump = true;

        auto frame = prepareNativeDrawDiagnostic(observed, lease, 11.01);
        static_assert(std::is_const_v<std::remove_reference_t<decltype(*frame)>>,
            "Published diagnostic frames must be immutable");
        require(bool(frame) && frame->lines.size() == 6, "Coherent observation did not produce bounded markers");
        require(frame->lines[0].start[0] == 80 && frame->lines[0].end[0] == 120 &&
            frame->lines[3].ball && frame->lines[3].start[0] == 280,
            "Car and ball markers did not use the same observation");
        require(frame->actions.jump && frame->actions.axes == observed.actions.axes &&
            frame->gameSeconds == observed.gameSeconds, "Observed actions/time were not preserved");
        observed.carPosition[0] = 999;
        observed.actions.jump = false;
        require(frame->lines[0].start[0] == 80 && frame->actions.jump, "Frame aliases mutable source data");
        observed.carPosition[0] = 100;
        observed.actions.jump = true;

        for (auto field : {&NativeDrawObservation::ownedOffline, &NativeDrawObservation::fresh,
                &NativeDrawObservation::buildVerified, &NativeDrawObservation::customTraining,
                &NativeDrawObservation::carObserved, &NativeDrawObservation::ballObserved,
                &NativeDrawObservation::actionsObserved}) {
            auto changed = observed;
            changed.*field = false;
            require(!prepareNativeDrawDiagnostic(changed, lease, 11.01), "Missing observed scope/data was admitted");
        }
        for (auto field : {&NativeDrawObservation::online, &NativeDrawObservation::replay,
                &NativeDrawObservation::paused}) {
            auto changed = observed;
            changed.*field = true;
            require(!prepareNativeDrawDiagnostic(changed, lease, 11.01), "Unsafe game mode was admitted");
        }
        for (int change = 0; change < 8; ++change) {
            auto changed = observed;
            switch (change) {
            case 0: ++changed.identity.pid; break;
            case 1: ++changed.identity.created; break;
            case 2: changed.identity.nonce += "-other"; break;
            case 3: ++changed.identity.event; break;
            case 4: ++changed.identity.car; break;
            case 5: ++changed.identity.ball; break;
            case 6: ++changed.identity.epoch; break;
            case 7: ++changed.identity.round; break;
            }
            require(!prepareNativeDrawDiagnostic(changed, lease, 11.01), "Identity/reset/round change retained visibility");
        }
        for (double now : {10.99, 11.11, 15.0, std::numeric_limits<double>::quiet_NaN()})
            require(!prepareNativeDrawDiagnostic(observed, lease, now), "Future/stale/expired observation was admitted");
        require(!nativeDrawFrameCurrent(*frame, lease, 11.11), "A cached frame outlived freshness");
        auto rebound = lease;
        ++rebound.identity.epoch;
        require(!nativeDrawFrameCurrent(*frame, rebound, 11.01), "A cached frame crossed a reset epoch");
        auto badLease = lease;
        badLease.expires = 16;
        require(!prepareNativeDrawDiagnostic(observed, badLease, 11.01), "Unbounded diagnostic lease was admitted");
        auto bad = observed;
        bad.ballPosition[2] = std::numeric_limits<float>::infinity();
        require(!prepareNativeDrawDiagnostic(bad, lease, 11.01), "Nonfinite position was admitted");
        bad = observed;
        bad.actions.axes[0] = 1.01f;
        require(!prepareNativeDrawDiagnostic(bad, lease, 11.01), "Invalid logical action was admitted");
        require(!prepareNativeDrawDiagnostic(NativeDrawObservation{}, NativeDrawLease{}, 0),
            "Default/unknown observations must not grant visibility");
        std::cout << "Native draw diagnostic core scope, immutable snapshot and expiry tests passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
