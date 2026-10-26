#include "TrainingGhostInput.h"

#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using mct::TrainingGhostInput;
using Json = TrainingGhostInput::Json;

static void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

static TrainingGhostInput::Scope liveScope() {
    TrainingGhostInput::Scope scope;
    scope.owned = true;
    scope.fresh = true;
    scope.foreground = true;
    scope.inGame = true;
    scope.online = false;
    return scope;
}

static Json trainingState() {
    return Json{
        {"bridge_session", "bridge-a"},
        {"offline", true},
        {"session", {
            {"id", "session-a"},
            {"kind", "training"},
            {"state", "training"},
            {"worker_running", true},
            {"busy", false}
        }},
        {"telemetry", {
            {"lesson_id", "speed-flip"},
            {"ghost_practice", {{"available", true}, {"enabled", false}}},
            {"ghost_practice_support", {{"supported", true}}},
            {"ghost_practice_pending", false}
        }}
    };
}

static TrainingGhostInput::Pad pad(bool left, int slot = 0) {
    return {slot, left};
}

static void startupHoldNeedsReleaseAndOneRisingEdgeTogglesOnce() {
    TrainingGhostInput input;
    const auto scope = liveScope();
    const auto state = trainingState();

    require(!input.observe(scope, state, pad(true), 0.0).toggle,
        "A left-D-pad already held at startup must not toggle");
    require(!input.observe(scope, state, pad(true), 0.01).toggle,
        "A held left-D-pad must not repeat");
    require(!input.observe(scope, state, pad(false), 0.02).toggle,
        "Release must arm the input without toggling");

    const auto on = input.observe(scope, state, pad(true), 0.03);
    require(on.toggle && on.enabled, "A fresh eligible left-D-pad press did not toggle On");
    require(on.session == "session-a" && on.lesson == "speed-flip",
        "Toggle decision did not carry its current training identity");
    require(input.latched(), "Toggle did not latch while acknowledgement is outstanding");
    require(!input.observe(scope, state, pad(true), 0.04).toggle,
        "Holding left-D-pad after the toggle sent a duplicate");
}

static void ineligiblePressIsConsumedUntilFreshRelease() {
    using Mutator = std::pair<const char*, std::function<void(TrainingGhostInput::Scope&, Json&)>>;
    const std::vector<Mutator> blocked = {
        {"unowned session", [](auto& s, auto&) { s.owned = false; }},
        {"stale bridge", [](auto& s, auto&) { s.fresh = false; }},
        {"background window", [](auto& s, auto&) { s.foreground = false; }},
        {"frontend", [](auto& s, auto&) { s.inGame = false; }},
        {"online match", [](auto& s, auto&) { s.online = true; }},
        {"replay", [](auto& s, auto&) { s.replay = true; }},
        {"pause", [](auto& s, auto&) { s.paused = true; }},
        {"ended match", [](auto& s, auto&) { s.matchEnded = true; }},
        {"native menu", [](auto& s, auto&) { s.nativeMenuActive = true; }},
        {"reference capture", [](auto& s, auto&) { s.referenceCaptureActive = true; }},
        {"career session", [](auto&, auto& j) { j["session"]["kind"] = "career"; }},
        {"non-training phase", [](auto&, auto& j) { j["session"]["state"] = "Career Ready"; }},
        {"missing worker", [](auto&, auto& j) { j["session"]["worker_running"] = false; }},
        {"busy worker", [](auto&, auto& j) { j["session"]["busy"] = true; }},
        {"missing lesson", [](auto&, auto& j) { j["telemetry"]["lesson_id"] = ""; }},
        {"pending command", [](auto&, auto& j) { j["telemetry"]["ghost_practice_pending"] = true; }},
        {"unsupported lesson", [](auto&, auto& j) {
            j["telemetry"]["ghost_practice_support"]["supported"] = false;
        }},
        {"no available recording", [](auto&, auto& j) {
            j["telemetry"]["ghost_practice"]["available"] = false;
        }},
        {"not offline", [](auto&, auto& j) { j["offline"] = false; }}
    };

    for (const auto& test : blocked) {
        TrainingGhostInput input;
        auto scope = liveScope();
        auto state = trainingState();
        input.observe(scope, state, pad(false), 0.0);

        test.second(scope, state);
        require(!input.observe(scope, state, pad(true), 0.01).toggle,
            "An ineligible scope sent a ghost command");

        scope = liveScope();
        state = trainingState();
        require(!input.observe(scope, state, pad(true), 0.02).toggle,
            "Returning to an eligible scope toggled while the button was still held");
        input.observe(scope, state, pad(false), 0.03);
        const auto retry = input.observe(scope, state, pad(true), 0.04);
        require(retry.toggle && retry.enabled,
            "A fresh press after an ineligible scope did not work");
    }
}

static void sessionOrLessonChangeWhileHeldRequiresFreshRelease() {
    using Change = std::pair<const char*, std::function<void(Json&)>>;
    const std::vector<Change> changes = {
        {"bridge session", [](Json& j) { j["bridge_session"] = "bridge-b"; }},
        {"activity session", [](Json& j) { j["session"]["id"] = "session-b"; }},
        {"lesson", [](Json& j) { j["telemetry"]["lesson_id"] = "flip-reset"; }}
    };

    for (const auto& change : changes) {
        TrainingGhostInput input;
        const auto scope = liveScope();
        auto state = trainingState();
        input.observe(scope, state, pad(false), 0.0);

        change.second(state);
        require(!input.observe(scope, state, pad(true), 0.01).toggle,
            "A held button crossed a changed session identity");
        require(!input.observe(scope, state, pad(true), 0.02).toggle,
            "A changed identity toggled before the button was released");

        input.observe(scope, state, pad(false), 0.03);
        const auto fresh = input.observe(scope, state, pad(true), 0.04);
        require(fresh.toggle && fresh.enabled,
            "A fresh post-transition press did not toggle");
        require(fresh.session == state["session"]["id"].get<std::string>() &&
                fresh.lesson == state["telemetry"]["lesson_id"].get<std::string>(),
            "Toggle decision used stale session or lesson identity");
    }
}

static void zeroOrMultipleControllersAndNewHeldSlotRequireFreshRelease() {
    TrainingGhostInput input;
    const auto scope = liveScope();
    const auto state = trainingState();

    require(!input.observe(scope, state, pad(false, -1), 0.0).toggle,
        "No connected controller toggled the ghost");
    require(!input.observe(scope, state, pad(true, -1), 0.01).toggle,
        "A left-D-pad report without exactly one controller toggled the ghost");
    require(!input.observe(scope, state, pad(true, 0), 0.02).toggle,
        "A new controller slot already held did not require release");
    input.observe(scope, state, pad(false, 0), 0.03);
    require(!input.observe(scope, state, pad(true, 1), 0.04).toggle,
        "A newly selected controller slot already held toggled the ghost");
    input.observe(scope, state, pad(false, 1), 0.05);
    const auto fresh = input.observe(scope, state, pad(true, 1), 0.06);
    require(fresh.toggle && fresh.enabled,
        "One controller with a fresh press could not toggle the ghost");
}

static void pendingAndAcknowledgementLatchPreventDuplicateEdges() {
    TrainingGhostInput input;
    const auto scope = liveScope();
    auto state = trainingState();
    input.observe(scope, state, pad(false), 0.0);
    require(input.observe(scope, state, pad(true), 0.01).toggle,
        "Initial On request was not sent");

    input.observe(scope, state, pad(false), 0.02);
    require(!input.observe(scope, state, pad(true), 0.03).toggle,
        "A second press while awaiting acknowledgement escaped the local latch");

    state["telemetry"]["ghost_practice_pending"] = true;
    input.observe(scope, state, pad(false), 0.04);
    require(!input.observe(scope, state, pad(true), 0.05).toggle,
        "A pending bridge command allowed another toggle edge");

    // The worker's acknowledged On state clears the local latch. The player
    // still needs a fresh press to send Off.
    state["telemetry"]["ghost_practice_pending"] = false;
    state["telemetry"]["ghost_practice"]["enabled"] = true;
    input.observe(scope, state, pad(false), 0.06);
    const auto off = input.observe(scope, state, pad(true), 0.07);
    require(off.toggle && !off.enabled, "Acknowledged On state did not permit one fresh Off edge");
    require(!input.observe(scope, state, pad(true), 0.08).toggle,
        "Holding after acknowledged Off sent a duplicate");
}

static void unsupportedOrUnavailableOnIsRefusedButEnabledOffIsAllowed() {
    TrainingGhostInput input;
    const auto scope = liveScope();
    auto state = trainingState();
    state["telemetry"]["ghost_practice_support"]["supported"] = false;
    state["telemetry"]["ghost_practice"]["available"] = false;

    input.observe(scope, state, pad(false), 0.0);
    require(!input.observe(scope, state, pad(true), 0.01).toggle,
        "Unsupported and unavailable practice allowed On");

    // A support change must not block the safety Off path for an already-on ghost.
    state["telemetry"]["ghost_practice"]["enabled"] = true;
    input.observe(scope, state, pad(false), 0.02);
    const auto off = input.observe(scope, state, pad(true), 0.03);
    require(off.toggle && !off.enabled,
        "Lost support blocked turning an already-enabled ghost Off");
}

static void observationDoesNotModifyTheControllerSample() {
    TrainingGhostInput input;
    const auto scope = liveScope();
    const auto state = trainingState();
    const TrainingGhostInput::Pad sample{0, false};
    input.observe(scope, state, sample, 0.0);
    require(sample.slot == 0 && !sample.dpadLeft,
        "Observing the controller changed the caller's input sample");
}

int main() {
    try {
        startupHoldNeedsReleaseAndOneRisingEdgeTogglesOnce();
        ineligiblePressIsConsumedUntilFreshRelease();
        sessionOrLessonChangeWhileHeldRequiresFreshRelease();
        zeroOrMultipleControllersAndNewHeldSlotRequireFreshRelease();
        pendingAndAcknowledgementLatchPreventDuplicateEdges();
        unsupportedOrUnavailableOnIsRefusedButEnabledOffIsAllowed();
        observationDoesNotModifyTheControllerSample();
        std::cout << "Training ghost controller edge and eligibility tests passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}

