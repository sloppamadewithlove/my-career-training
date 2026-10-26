#include "NativeMatchLayout.h"

#include <iostream>
#include <stdexcept>
#include <string>

using namespace mct;

static void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

static CareerLayoutScope pauseScope() {
    return {true, true, true, false, "123e4567-e89b-12d3-a456-426614174000", 1,
            NativeMenuSurface::Pause};
}

static Json trainingState(const CareerLayoutScope& scope) {
    return Json{
        {"protocol", 1}, {"offline", true}, {"bridge_session", scope.nonce},
        {"session", {{"id", "123e4567-e89b-12d3-a456-426614174001"}, {"fixture_id", ""},
            {"kind", "training"}, {"state", "training"}, {"worker_running", true},
            {"busy", false}, {"can_exit", true}}},
        {"telemetry", {{"lesson_id", "speed-flip"}}}
    };
}

static const CareerLayoutChoice& findChoice(const CareerLayoutView& view, const std::string& id) {
    for (const auto& choice : view.choices)
        if (choice.id == id) return choice;
    throw std::runtime_error("Expected native training option missing: " + id);
}

static bool hasChoice(const CareerLayoutView& view, const std::string& id) {
    for (const auto& choice : view.choices)
        if (choice.id == id) return true;
    return false;
}

static void enterTrainingOptions(NativeMatchLayout& layout, const CareerLayoutScope& scope,
                                 const Json& state) {
    const auto root = layout.view(scope, state);
    const auto& entry = findChoice(root, "pause.training_options");
    require(entry.enabled && entry.kind == CareerLayoutEffectKind::Navigate,
        "A live lesson did not expose Training options navigation");
    const auto entered = layout.choose(entry, scope, state, false);
    require(entered.accepted && entered.kind == CareerLayoutEffectKind::Navigate,
        "Training options navigation was not accepted as a local page change");
}

static void fourLessonTogglesHaveStableDefaultAndOffPayloads() {
    auto scope = pauseScope();
    auto state = trainingState(scope);
    NativeMatchLayout layout;
    require(layout.open(scope, state), "Training pause did not open");
    enterTrainingOptions(layout, scope, state);

    const struct Toggle { const char* id; const char* key; const char* label; } toggles[] = {
        {"pause.training_instructions", "explanations", "Instructions"},
        {"pause.training_controller", "actions", "Controller"},
        {"pause.training_timing", "timing", "Timing feedback"},
        {"pause.training_retry_after", "auto_reset", "Retry after attempt"},
    };
    auto view = layout.view(scope, state);
    require(view.title == "Training options", "The selected page did not identify Training options");
    for (const auto& toggle : toggles) {
        const auto& choice = findChoice(view, toggle.id);
        const Json expected = {{"id", "speed-flip"}, {"key", toggle.key}, {"value", false}};
        require(choice.enabled && choice.kind == CareerLayoutEffectKind::Dispatch &&
                choice.action == "assistance" && choice.payload == expected,
            "A default-On training preference did not dispatch its exact Off payload");
        require(choice.label == std::string(toggle.label) + ": On",
            "A missing lesson preference did not display its default On state");
        const auto effect = layout.choose(choice, scope, state, true);
        require(effect.accepted && effect.action == "assistance" && effect.payload == expected,
            "Training preference click changed its action or payload");
        // choose() advances the revision; refresh as the movie host does after
        // consuming a button click before checking the next control.
        view = layout.view(scope, state);
    }

    state["lesson_preferences"]["speed-flip"] = {
        {"explanations", false}, {"actions", false}, {"timing", false}, {"auto_reset", false}};
    // Re-enter from the parent menu, then verify that explicit false values are
    // rendered Off and that each click requests the inverse value.
    auto root = layout.view(scope, state);
    if (!hasChoice(root, "pause.training_options")) {
        const auto& back = findChoice(root, "pause.training_options_back");
        require(layout.choose(back, scope, state, false).accepted,
            "Back from Training options was not accepted");
        root = layout.view(scope, state);
    }
    const auto& entry = findChoice(root, "pause.training_options");
    require(layout.choose(entry, scope, state, false).accepted,
        "Training options could not be reopened to verify saved Off states");
    view = layout.view(scope, state);
    for (const auto& toggle : toggles) {
        const auto& choice = findChoice(view, toggle.id);
        const Json expected = {{"id", "speed-flip"}, {"key", toggle.key}, {"value", true}};
        require(choice.enabled && choice.label == std::string(toggle.label) + ": Off" &&
                choice.payload == expected,
            "An explicit Off preference did not display and request the inverse On state");
    }
}

static void backReturnsToPauseAndStaleButtonsAreRejected() {
    auto scope = pauseScope();
    auto state = trainingState(scope);
    NativeMatchLayout layout;
    require(layout.open(scope, state), "Training pause did not open");
    enterTrainingOptions(layout, scope, state);
    const auto subpage = layout.view(scope, state);
    const auto stale = findChoice(subpage, "pause.training_controller");

    // A state change after rendering invalidates the previously shown command.
    state["lesson_preferences"]["speed-flip"]["actions"] = false;
    const auto staleEffect = layout.choose(stale, scope, state, true);
    require(!staleEffect.accepted && staleEffect.action.empty(),
        "A stale controller toggle was accepted after its displayed value changed");

    const auto fresh = layout.view(scope, state);
    const auto& back = findChoice(fresh, "pause.training_options_back");
    const auto backEffect = layout.choose(back, scope, state, false);
    require(backEffect.accepted && backEffect.kind == CareerLayoutEffectKind::Navigate,
        "The explicit Back button did not return from the local options page");
    const auto root = layout.view(scope, state);
    require(root.title != "Training options" && hasChoice(root, "pause.resume") &&
            hasChoice(root, "pause.training_options"),
        "Back did not restore the parent Training pause menu");
    require(!layout.choose(stale, scope, state, true).accepted,
        "A subpage action remained usable after returning to the parent menu");
}

static void changedLessonOrSessionInvalidatesTheLocalPage() {
    auto scope = pauseScope();
    auto state = trainingState(scope);
    NativeMatchLayout layout;
    require(layout.open(scope, state), "Training pause did not open");
    enterTrainingOptions(layout, scope, state);
    const auto staleLesson = findChoice(layout.view(scope, state), "pause.training_controller");
    state["telemetry"]["lesson_id"] = "flip-reset";
    auto view = layout.view(scope, state);
    require(view.title != "Training options" && hasChoice(view, "pause.training_options"),
        "Changing lessons left the old lesson's options page open");
    require(!layout.choose(staleLesson, scope, state, true).accepted,
        "A command bound to the previous lesson was accepted");

    enterTrainingOptions(layout, scope, state);
    const auto staleSession = findChoice(layout.view(scope, state), "pause.training_timing");
    state["session"]["id"] = "123e4567-e89b-12d3-a456-426614174099";
    view = layout.view(scope, state);
    require(view.title != "Training options" && hasChoice(view, "pause.training_options"),
        "Changing sessions left the previous session's options page open");
    require(!layout.choose(staleSession, scope, state, true).accepted,
        "A command bound to the previous session was accepted");
}

static void returnPendingAndLostScopeCloseTheSubpage() {
    auto scope = pauseScope();
    auto state = trainingState(scope);
    NativeMatchLayout layout;
    require(layout.open(scope, state), "Training pause did not open");
    enterTrainingOptions(layout, scope, state);
    const auto stale = findChoice(layout.view(scope, state), "pause.training_retry_after");

    auto pending = layout.view(scope, state, true, true);
    require(pending.title != "Training options" && !hasChoice(pending, "pause.training_options_back") &&
            hasChoice(pending, "pause.resume"),
        "Pending Return did not close Training options and expose recovery controls");
    require(!findChoice(pending, "pause.resume").enabled,
        "Return hold left Resume active while cleanup was pending");
    require(!layout.choose(stale, scope, state, true, true, true).accepted,
        "A lesson option was accepted after Return became pending");

    auto restored = layout.view(scope, state);
    require(restored.title != "Training options" && hasChoice(restored, "pause.training_options"),
        "Training options did not reset to the parent menu after Return cleared");
    require(!layout.choose(stale, scope, state, true).accepted,
        "A pre-Return option command remained accepted after cleanup");

    enterTrainingOptions(layout, scope, state);
    const auto staleAfterScopeLoss = findChoice(layout.view(scope, state), "pause.training_instructions");
    auto lost = scope;
    lost.owned = false;
    const auto unavailable = layout.view(lost, state);
    require(!unavailable.offersReplacement && unavailable.choices.empty(),
        "The native page remained offered after ownership was lost");
    require(!layout.choose(staleAfterScopeLoss, lost, state, true).accepted,
        "A stale lesson option was accepted after ownership was lost");
    const auto recovered = layout.view(scope, state);
    require(recovered.title != "Training options" && hasChoice(recovered, "pause.training_options"),
        "The local page did not reset after scope was reacquired");
}

int main() {
    try {
        fourLessonTogglesHaveStableDefaultAndOffPayloads();
        backReturnsToPauseAndStaleButtonsAreRejected();
        changedLessonOrSessionInvalidatesTheLocalPage();
        returnPendingAndLostScopeCloseTheSubpage();
        std::cout << "Native Training options contracts passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
