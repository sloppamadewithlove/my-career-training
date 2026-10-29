#include "TrainingLessonInput.h"

#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>

using mct::TrainingBindingGuard;
using mct::TrainingHudLayout;
using mct::TrainingHudModel;
using mct::TrainingLessonInput;
using Json = TrainingLessonInput::Json;

static void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

static TrainingLessonInput::Scope liveScope() {
    TrainingLessonInput::Scope scope;
    scope.owned = true;
    scope.fresh = true;
    scope.foreground = true;
    scope.inGame = true;
    scope.online = false;
    return scope;
}

static Json trainingState() {
    return {
        {"bridge_session", "bridge-a"}, {"offline", true},
        {"session", {{"id", "session-a"}, {"kind", "training"}, {"state", "training"},
            {"worker_running", true}, {"busy", false}}},
        {"telemetry", {{"lesson_id", "power-shots"},
            {"coaching", {{"scenario_index", 3}, {"scenario_total", 12}, {"scenario_title", "Near-post strike"},
                {"rank_title", "Silver"}, {"time_limit_seconds", 30.0}, {"time_remaining_seconds", 12.4},
                {"phase", "ready"}, {"attempt_id", "attempt-a"}, {"countdown", "READY"}}},
            {"ghost_practice", {{"available", true}, {"enabled", false}}},
            {"ghost_practice_support", {{"supported", true}}}, {"ghost_practice_pending", false}}}
    };
}

static TrainingLessonInput::Pad pad(bool left = false, bool right = false, bool up = false,
                                     bool down = false, int slot = 0) {
    return {slot, left, right, up, down};
}

static TrainingLessonInput::Decision freshPress(TrainingLessonInput& input,
                                                 TrainingLessonInput::Scope scope, Json state,
                                                 TrainingLessonInput::Pad pressed) {
    input.observe(scope, state, pad(false, false, false, false, pressed.slot), 0.0);
    return input.observe(scope, state, pressed, 0.01);
}

static void allFourActionsAreEdges() {
    const auto scope = liveScope();
    const auto state = trainingState();
    struct Case { TrainingLessonInput::Pad sample; TrainingLessonInput::Action action; };
    const Case cases[] = {
        {pad(true), TrainingLessonInput::Action::Previous},
        {pad(false, true), TrainingLessonInput::Action::Next},
        {pad(false, false, false, true), TrainingLessonInput::Action::ToggleGhost},
        {pad(false, false, true), TrainingLessonInput::Action::Retry},
    };
    for (const auto& test : cases) {
        TrainingLessonInput input;
        const auto decision = freshPress(input, scope, state, test.sample);
        require(decision.action == test.action, "A lesson D-pad edge mapped to the wrong action");
        require(input.observe(scope, state, test.sample, 0.02).action == TrainingLessonInput::Action::None,
            "A held D-pad direction repeated");
    }
}

static void scopeAndIdentityChangesRequireRelease() {
    const auto state = trainingState();
    struct Block { const char* name; std::function<void(TrainingLessonInput::Scope&, Json&)> apply; };
    const Block blocks[] = {
        {"focus", [](auto& scope, auto&) { scope.foreground = false; }},
        {"pause", [](auto& scope, auto&) { scope.paused = true; }},
        {"online", [](auto& scope, auto&) { scope.online = true; }},
        {"replay", [](auto& scope, auto&) { scope.replay = true; }},
        {"menu", [](auto& scope, auto&) { scope.nativeMenuActive = true; }},
        {"career", [](auto&, auto& json) { json["session"]["kind"] = "career"; }},
    };
    for (const auto& block : blocks) {
        TrainingLessonInput input;
        auto scope = liveScope();
        auto current = state;
        input.observe(scope, current, pad(), 0.0);
        block.apply(scope, current);
        require(input.observe(scope, current, pad(true), 0.01).action == TrainingLessonInput::Action::None,
            "An ineligible lesson dispatched");
        scope = liveScope(); current = state;
        require(input.observe(scope, current, pad(true), 0.02).action == TrainingLessonInput::Action::None,
            "A held direction fired after scope restoration");
        input.observe(scope, current, pad(), 0.03);
        require(input.observe(scope, current, pad(true), 0.04).action == TrainingLessonInput::Action::Previous,
            "A released direction did not re-arm");
    }

    TrainingLessonInput input;
    auto current = state;
    input.observe(liveScope(), current, pad(), 0.0);
    current["session"]["id"] = "session-b";
    require(input.observe(liveScope(), current, pad(true), 0.01).action == TrainingLessonInput::Action::None,
        "A held direction crossed a session change");
    require(input.observe(liveScope(), current, pad(false, false, false, false, 1), 0.02).action == TrainingLessonInput::Action::None,
        "A controller-slot change dispatched");
    require(input.observe(liveScope(), current, pad(true, false, false, false, 2), 0.03).action == TrainingLessonInput::Action::None,
        "A held direction crossed a controller-slot change");
}

static void acknowledgementsAndGhostAvailabilityFailClosed() {
    auto state = trainingState();
    TrainingLessonInput input;
    require(freshPress(input, liveScope(), state, pad(true)).action == TrainingLessonInput::Action::Previous,
        "Initial scenario step missing");
    input.commandSent("command-a");
    input.observe(liveScope(), state, pad(), 0.02);
    require(input.observe(liveScope(), state, pad(false, true), 0.03).action == TrainingLessonInput::Action::None,
        "A second action escaped the acknowledgement latch");
    state["command_ack"] = {{"id", "stale-command"}, {"ok", false}, {"error", "stale"}};
    input.observe(liveScope(), state, pad(), 0.04);
    require(input.latched(), "A stale failed command acknowledgement cleared the latch");
    state["command_ack"] = {{"id", "command-a"}, {"ok", true}, {"error", ""}};
    input.observe(liveScope(), state, pad(), 0.05);
    require(input.latched(), "A successful dispatch acknowledgement cleared the runtime latch early");
    state["command_ack"] = {{"id", "command-a"}, {"ok", false}, {"error", "rejected"}};
    require(input.observe(liveScope(), state, pad(false, true), 0.06).action == TrainingLessonInput::Action::Next,
        "The exact rejected command swallowed the next released D-pad press");

    state = trainingState();
    TrainingLessonInput retry;
    require(freshPress(retry, liveScope(), state, pad(false, false, true)).action ==
            TrainingLessonInput::Action::Retry,
        "Initial retry missing");
    retry.commandSent("retry-a");
    retry.observe(liveScope(), state, pad(), 0.02);
    state["command_ack"] = {{"id", "retry-a"}, {"ok", true}, {"error", ""}};
    retry.observe(liveScope(), state, pad(), 0.03);
    require(retry.latched(), "Retry dispatch acknowledgement replaced the worker reset acknowledgement");
    state["telemetry"]["coaching"]["phase"] = "settle";
    retry.observe(liveScope(), state, pad(), 0.035);
    require(retry.latched(), "A phase change alone acknowledged retry");
    state["telemetry"]["coaching"]["attempt_id"] = "attempt-b";
    state["telemetry"]["coaching"]["phase"] = "active";
    retry.observe(liveScope(), state, pad(), 0.04);
    require(!retry.latched(), "The worker retry transition did not release the latch");
    retry.observe(liveScope(), state, pad(), 0.05);
    state["telemetry"]["coaching"]["phase"] = "ready";
    require(retry.observe(liveScope(), state, pad(false, false, true), 0.06).action ==
            TrainingLessonInput::Action::Retry,
        "A completed retry transition did not promptly re-arm after release");

    state = trainingState();
    state["telemetry"]["coaching"]["scenario_index"] = 1;
    TrainingLessonInput scenario;
    require(freshPress(scenario, liveScope(), state, pad(true)).action == TrainingLessonInput::Action::Previous,
        "Scenario acknowledgement setup failed");
    scenario.commandSent("scenario-a");
    scenario.observe(liveScope(), state, pad(), 0.02);
    state["telemetry"]["coaching"]["scenario_index"] = 12;
    scenario.observe(liveScope(), state, pad(), 0.03);
    require(!scenario.latched(), "Wrapped scenario transition did not release the latch");

    state = trainingState();
    TrainingLessonInput busyOnly;
    require(freshPress(busyOnly, liveScope(), state, pad(true)).action == TrainingLessonInput::Action::Previous,
        "Busy-only acknowledgement setup failed");
    busyOnly.commandSent("busy-a");
    state["session"]["busy"] = true;
    busyOnly.observe(liveScope(), state, pad(), 0.02);
    state["session"]["busy"] = false;
    busyOnly.observe(liveScope(), state, pad(), 0.03);
    require(busyOnly.latched(), "An unrelated busy transition cleared the runtime latch");

    state = trainingState();
    state["telemetry"]["ghost_practice"]["available"] = false;
    state["telemetry"]["ghost_practice_support"]["supported"] = false;
    TrainingLessonInput unavailable;
    require(freshPress(unavailable, liveScope(), state, pad(false, false, false, true)).action == TrainingLessonInput::Action::None,
        "Unavailable ghost trace was toggled");
    state["telemetry"]["ghost_practice"]["enabled"] = true;
    TrainingLessonInput enabled;
    const auto off = freshPress(enabled, liveScope(), state, pad(false, false, false, true));
    require(off.action == TrainingLessonInput::Action::ToggleGhost && !off.ghostEnabled,
        "An enabled ghost could not be turned off after support loss");
}

static void retryWhileSettlingUsesAttemptAcknowledgement() {
    auto state = trainingState();
    state["telemetry"]["coaching"]["phase"] = "settle";
    state["telemetry"]["coaching"]["attempt_id"] = "attempt-a";
    TrainingLessonInput input;
    require(freshPress(input, liveScope(), state, pad(false, false, true)).action ==
        TrainingLessonInput::Action::Retry, "Up did not retry while preparing");
    input.observe(liveScope(), state, pad(), .02);
    state["telemetry"]["coaching"]["attempt_id"] = "attempt-b";
    input.observe(liveScope(), state, pad(), .03);
    require(!input.latched(), "Same-phase reset did not acknowledge new attempt");
    require(input.observe(liveScope(), state, pad(false, false, true), .04).action ==
        TrainingLessonInput::Action::Retry, "Separate Up press was swallowed");
}

static void bindingsRestoreExactlyAndRespectExternalChanges() {
    std::map<std::string, std::string> bindings{{TrainingBindingGuard::keys[0], "old_left"},
        {TrainingBindingGuard::keys[1], TrainingBindingGuard::commands[1]},
        {TrainingBindingGuard::keys[2], "old_up"}};
    const auto read = [&](const std::string& key) {
        const auto found = bindings.find(key);
        return found == bindings.end() ? std::string{} : found->second;
    };
    const auto write = [&](const std::string& key, const std::string& value) { bindings[key] = value; };
    const auto remove = [&](const std::string& key) { bindings.erase(key); };
    TrainingBindingGuard guard;
    require(guard.acquire(read, write, remove), "Scoped lesson bindings were not acquired");
    for (std::size_t index = 0; index < TrainingBindingGuard::keys.size(); ++index)
        require(bindings[TrainingBindingGuard::keys[index]] == TrainingBindingGuard::commands[index],
            "A D-pad binding was not scoped to the lesson command");
    bindings[TrainingBindingGuard::keys[1]] = "user_changed_it";
    guard.release(read, write, remove);
    require(bindings[TrainingBindingGuard::keys[0]] == "old_left" &&
            bindings[TrainingBindingGuard::keys[1]] == "user_changed_it" &&
            bindings[TrainingBindingGuard::keys[2]] == "old_up",
        "Existing bindings were not restored");
    require(bindings.count(TrainingBindingGuard::keys[3]) == 0,
        "A previously empty binding was left behind");
    require(bindings[TrainingBindingGuard::keys[1]] == "user_changed_it",
        "An external binding change was overwritten during restoration");

    bindings = {{TrainingBindingGuard::keys[1], TrainingBindingGuard::commands[1]}};
    TrainingBindingGuard exact;
    require(exact.acquire(read, write, remove), "An existing owned command could not be scoped");
    require(exact.release(read, write, remove), "An existing owned command could not be restored");
    require(bindings[TrainingBindingGuard::keys[1]] == TrainingBindingGuard::commands[1],
        "An exact prior owned command was not preserved");
}

static void bindingFailuresRollBackAndRemainRetryable() {
    std::map<std::string, std::string> bindings{{TrainingBindingGuard::keys[0], "old_left"},
        {TrainingBindingGuard::keys[1], "old_right"}, {TrainingBindingGuard::keys[2], "old_up"}};
    const auto read = [&](const std::string& key) {
        const auto found = bindings.find(key);
        return found == bindings.end() ? std::string{} : found->second;
    };
    const auto remove = [&](const std::string& key) { bindings.erase(key); };
    TrainingBindingGuard partial;
    const auto partialWrite = [&](const std::string& key, const std::string& value) {
        if (key == TrainingBindingGuard::keys[2] && value == TrainingBindingGuard::commands[2])
            throw std::runtime_error("synthetic bind failure");
        bindings[key] = value;
    };
    require(!partial.acquire(read, partialWrite, remove), "A partial binding failure was accepted");
    require(bindings[TrainingBindingGuard::keys[0]] == "old_left" &&
            bindings[TrainingBindingGuard::keys[1]] == "old_right" &&
            bindings[TrainingBindingGuard::keys[2]] == "old_up" &&
            bindings.count(TrainingBindingGuard::keys[3]) == 0,
        "A partial binding failure was not rolled back exactly");

    const auto write = [&](const std::string& key, const std::string& value) { bindings[key] = value; };
    TrainingBindingGuard release;
    require(release.acquire(read, write, remove), "Release retry setup could not acquire bindings");
    bool failOnce = true;
    const auto unreliableWrite = [&](const std::string& key, const std::string& value) {
        if (failOnce && key == TrainingBindingGuard::keys[0] && value == "old_left") {
            failOnce = false;
            throw std::runtime_error("synthetic restore failure");
        }
        bindings[key] = value;
    };
    require(!release.release(read, unreliableWrite, remove) && !release.active(),
        "A failed restoration erased its retryable state");
    require(release.release(read, unreliableWrite, remove) && !release.active(),
        "A failed restoration could not be retried");
    require(bindings[TrainingBindingGuard::keys[0]] == "old_left",
        "A retried restoration did not verify the prior value");

    bindings = {{TrainingBindingGuard::keys[0], "old_left"}, {TrainingBindingGuard::keys[1], "old_right"},
        {TrainingBindingGuard::keys[2], "old_up"}};
    TrainingBindingGuard stuck;
    require(stuck.acquire(read, write, remove), "Stuck release setup could not acquire bindings");
    bool restoreFails = true;
    const auto stuckWrite = [&](const std::string& key, const std::string& value) {
        if (restoreFails && value.rfind("old_", 0) == 0) throw std::runtime_error("synthetic persistent restore failure");
        bindings[key] = value;
    };
    require(!stuck.release(read, stuckWrite, remove) && !stuck.active(),
        "A failed release left the guard active");
    require(!stuck.acquire(read, stuckWrite, remove) && !stuck.active(),
        "Acquire accepted partially restored bindings while the restore failure persisted");
    restoreFails = false;
    require(stuck.acquire(read, write, remove), "Recovery could not reacquire bindings after a failed release");
    for (std::size_t index = 0; index < TrainingBindingGuard::keys.size(); ++index)
        require(bindings[TrainingBindingGuard::keys[index]] == TrainingBindingGuard::commands[index],
            "Recovery did not reacquire every D-pad binding");
    require(stuck.release(read, write, remove) && !stuck.active(), "The final release after recovery failed");
    require(bindings[TrainingBindingGuard::keys[0]] == "old_left" &&
            bindings[TrainingBindingGuard::keys[1]] == "old_right" &&
            bindings[TrainingBindingGuard::keys[2]] == "old_up" &&
            bindings.count(TrainingBindingGuard::keys[3]) == 0,
        "The final release did not restore the original bindings");
}

static void hudUsesOnlyValidatedMetadataAndStaysInTheTopSafeArea() {
    auto state = trainingState();
    auto model = TrainingHudModel::fromState(state);
    require(model.active && model.powerShots && model.scenarioKnown && model.scenarioIndex == 3 && model.scenarioTotal == 12,
        "Valid coaching metadata was not represented");
    require(model.timerKnown && model.timeRemaining == 12.4 && model.timeLimit == 30.0,
        "Valid countdown bounds changed");
    require(model.countdown == "READY", "Stable coaching countdown label was not represented");
    state["telemetry"]["coaching"]["scenario_total"] = "12";
    state["telemetry"]["coaching"]["time_remaining_seconds"] = 90.0;
    model = TrainingHudModel::fromState(state);
    require(!model.scenarioKnown && model.scenarioTotal == 0,
        "Missing numeric scenario metadata invented a total");
    require(model.timerKnown && model.timeRemaining == model.timeLimit,
        "Remaining time was not clamped to its finite limit");
    state["telemetry"]["coaching"]["countdown"] = "invented";
    require(TrainingHudModel::fromState(state).countdown.empty(), "Unknown countdown label reached the HUD");
    state["telemetry"]["coaching"]["time_limit_seconds"] = std::numeric_limits<double>::infinity();
    require(!TrainingHudModel::fromState(state).timerKnown, "Infinite timer metadata reached the HUD");

    for (const auto size : {std::pair<float, float>{1920.0f, 1080.0f}, {1280.0f, 720.0f}}) {
        const auto layout = TrainingHudLayout::forScreen(size.first, size.second);
        require(layout.fits(size.first, size.second), "Training HUD left the 1080p/720p safe area");
        require(layout.cardTop + layout.cardHeight < size.second / 2,
            "Training HUD entered the score/chat/boost lower region");
    }
}

int main() {
    try {
        allFourActionsAreEdges();
        retryWhileSettlingUsesAttemptAcknowledgement();
        scopeAndIdentityChangesRequireRelease();
        acknowledgementsAndGhostAvailabilityFailClosed();
        bindingsRestoreExactlyAndRespectExternalChanges();
        bindingFailuresRollBackAndRemainRetryable();
        hudUsesOnlyValidatedMetadataAndStaysInTheTopSafeArea();
        std::cout << "Lesson D-pad, scoped bindings and HUD model tests passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
