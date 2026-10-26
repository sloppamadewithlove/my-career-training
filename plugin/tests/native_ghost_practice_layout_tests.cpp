#include "NativeMatchLayout.h"

#include <iostream>
#include <stdexcept>
#include <string>

using namespace mct;

static void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

static bool hasAction(const CareerLayoutView& view, const std::string& action) {
    for (const auto& choice : view.choices)
        if (choice.action == action) return true;
    return false;
}

static const CareerLayoutChoice& findAction(const CareerLayoutView& view, const std::string& action,
                                             const Json& payload = Json::object()) {
    for (const auto& choice : view.choices)
        if (choice.action == action && (payload.empty() || choice.payload == payload)) return choice;
    throw std::runtime_error("Expected ghost-practice control missing: action=" + action +
                             " payload=" + payload.dump());
}

static std::string recordingId(std::uint64_t value) {
    static constexpr char digits[] = "0123456789abcdef";
    std::string suffix(12, '0');
    for (int index = 11; index >= 0; --index) {
        suffix[static_cast<std::size_t>(index)] = digits[value & 0xf];
        value >>= 4;
    }
    return "123e4567-e89b-12d3-a456-" + suffix;
}

static CareerLayoutScope pauseScope() {
    return {true, true, true, false, "123e4567-e89b-12d3-a456-426614174000", 1,
            NativeMenuSurface::Pause};
}

static Json practiceState(const CareerLayoutScope& scope) {
    const Json variant = {{"side", "right"}, {"angle", "center"}};
    const Json practice = {{"available", false}, {"enabled", false}, {"visible", false},
        {"status", "off"}, {"label", "Your Best Attempt"}};
    const Json support = {{"supported", true}, {"reason", ""}};
    const Json telemetry = {{"lesson_id", "speed-flip"}, {"lesson_variant", variant},
        {"ghost_practice", practice}, {"ghost_practice_support", support}};
    return Json{
        {"protocol", 1}, {"offline", true}, {"bridge_session", scope.nonce},
        {"session", {{"id", "123e4567-e89b-12d3-a456-426614174001"}, {"fixture_id", ""},
            {"kind", "training"}, {"state", "training"}, {"worker_running", true},
            {"busy", false}, {"can_exit", true}}},
        {"telemetry", telemetry},
        {"recordings", Json::array({
            {{"id", "123e4567-e89b-12d3-a456-426614174002"}, {"lesson_id", "speed-flip"},
                {"filename", "private-recording.json"}, {"label", "Your Best Attempt"},
                {"source", {{"kind", "local_player"}}}, {"outcome", "success"}, {"variant", variant}},
            {{"id", "123e4567-e89b-12d3-a456-426614174003"}, {"lesson_id", "speed-flip"},
                {"filename", "other-variant.json"}, {"label", "Other setup"},
                {"outcome", "success"}, {"variant", {{"side", "left"}, {"angle", "center"}}}},
            {{"id", "123e4567-e89b-12d3-a456-426614174004"}, {"lesson_id", "speed-flip"},
                {"filename", "unfinished.json"}, {"label", "Unfinished"},
                {"outcome", "unfinished"}, {"variant", variant}},
            {{"id", "123e4567-e89b-12d3-a456-426614174005"}, {"lesson_id", "flip-reset"},
                {"filename", "other-lesson.json"}, {"label", "Another lesson"},
                {"outcome", "success"}, {"variant", variant}}
        })}
    };
}

static void selectedRecordingUsesOnlyTheSavedId() {
    auto scope = pauseScope();
    auto state = practiceState(scope);
    NativeMatchLayout layout;
    require(layout.open(scope, state), "Training pause scope did not open");
    auto view = layout.view(scope, state);
    const Json expected = {{"id", "speed-flip"}, {"recording_id", "123e4567-e89b-12d3-a456-426614174002"}};
    const auto& choice = findAction(view, "play_recording", expected);
    require(choice.kind == CareerLayoutEffectKind::Dispatch && choice.enabled,
        "Compatible saved recording was not selectable");
    require(!choice.payload.contains("filename") && !choice.payload.contains("path"),
        "Native view exposed a local recording path");
    require(choice.label.find("personal") != std::string::npos &&
            choice.label.find("expert") == std::string::npos,
        "Personal recording was not honestly distinguished from an expert reference");
    for (const auto& row : view.choices) {
        if (row.action != "play_recording") continue;
        require(row.payload.value("recording_id", "") != "123e4567-e89b-12d3-a456-426614174003",
            "Native view offered a recording from a different lesson variation");
    }
    require(NativeCareerLayout::supportedAction("play_recording"),
        "Native movie host rejected the saved-recording action");
    require(LocalBridge::allowedAction("play_recording"),
        "Native local bridge rejected the saved-recording action");

    auto unconsumed = layout.choose(choice, scope, state, false);
    require(!unconsumed.accepted && unconsumed.action.empty(),
        "Recording selection dispatched before the original button click was consumed");
    auto selected = layout.choose(choice, scope, state, true);
    require(selected.accepted && selected.action == "play_recording" && selected.payload == expected,
        "Recording selection did not preserve the exact bridge payload");
}

static void recordingScanKeepsTheNewestSixtyFourAttempts() {
    auto scope = pauseScope();
    auto state = practiceState(scope);
    state["recordings"] = Json::array();
    const auto variant = state["telemetry"]["lesson_variant"];
    for (std::uint64_t index = 0; index < 70; ++index) {
        state["recordings"].push_back({{"id", recordingId(index)}, {"lesson_id", "speed-flip"},
            {"label", "Attempt " + std::to_string(index)}, {"source", {{"kind", "local_player"}}},
            {"outcome", "unfinished"}, {"variant", variant}});
    }

    NativeMatchLayout layout;
    require(layout.open(scope, state), "Training pause scope did not open with recording history");
    const auto view = layout.view(scope, state);
    const Json latest = {{"id", "speed-flip"}, {"recording_id", recordingId(69)}};
    findAction(view, "play_recording", latest);
    for (const auto& choice : view.choices) {
        if (choice.action != "play_recording") continue;
        require(choice.payload.value("recording_id", "") != recordingId(0),
            "The bounded native list retained old attempts and skipped the newest history");
    }
}

static void toggleIsSupportedAvailableAndToggleOnly() {
    auto scope = pauseScope();
    auto state = practiceState(scope);
    state["telemetry"]["ghost_practice"]["available"] = true;
    state["telemetry"]["ghost_practice"]["enabled"] = false;
    NativeMatchLayout layout;
    require(layout.open(scope, state), "Training pause scope did not open for toggle");
    auto view = layout.view(scope, state);
    const Json expected = {{"operation", "toggle"}, {"enabled", true}};
    const auto& choice = findAction(view, "ghost_control", expected);
    require(choice.kind == CareerLayoutEffectKind::Dispatch && choice.enabled,
        "Loaded supported recording did not expose ghost On");
    require(NativeCareerLayout::supportedAction("ghost_control"),
        "Native movie host rejected the ghost toggle action");
    require(LocalBridge::allowedAction("ghost_control"),
        "Native local bridge rejected the ghost toggle action");

    state["telemetry"]["ghost_practice_pending"] = true;
    view = layout.view(scope, state);
    const auto& pending = findAction(view, "ghost_control", expected);
    require(!pending.enabled && !pending.reason.empty(),
        "Pending ghost command did not disable the next toggle edge");
    state["telemetry"]["ghost_practice_pending"] = false;
    view = layout.view(scope, state);
    const auto& ready = findAction(view, "ghost_control", expected);

    auto unconsumed = layout.choose(ready, scope, state, false);
    require(!unconsumed.accepted && unconsumed.action.empty(),
        "Ghost toggle dispatched before the original button click was consumed");
    auto toggled = layout.choose(ready, scope, state, true);
    require(toggled.accepted && toggled.action == "ghost_control" && toggled.payload == expected,
        "Ghost toggle did not use the fixed On payload");

    state["telemetry"]["ghost_practice"]["enabled"] = true;
    require(layout.open(scope, state), "Training pause scope did not reopen for Off");
    view = layout.view(scope, state);
    const Json off = {{"operation", "toggle"}, {"enabled", false}};
    const auto& offChoice = findAction(view, "ghost_control", off);
    require(offChoice.enabled, "Loaded supported recording did not expose ghost Off");

    for (const auto& choice : view.choices) {
        if (choice.action == "ghost_control")
            require(choice.payload.size() == 2 && choice.payload.at("operation") == "toggle",
                "Practice flow exposed a pause, rate, seek, or loop control");
    }
}

static void unsupportedAndNonTrainingActivitiesHidePracticeControls() {
    auto scope = pauseScope();
    auto state = practiceState(scope);
    state["telemetry"]["ghost_practice"]["available"] = true;
    state["telemetry"]["ghost_practice_support"]["supported"] = false;
    NativeMatchLayout layout;
    require(layout.open(scope, state), "Unsupported training pause did not open");
    auto view = layout.view(scope, state);
    require(!hasAction(view, "ghost_control") && !hasAction(view, "play_recording"),
        "Unsupported drill offered translated ghost practice");

    state["telemetry"]["ghost_practice"]["enabled"] = true;
    state["telemetry"]["ghost_practice"]["available"] = false;
    require(layout.open(scope, state), "Unsupported active ghost pause did not open");
    view = layout.view(scope, state);
    const Json off = {{"operation", "toggle"}, {"enabled", false}};
    require(findAction(view, "ghost_control", off).enabled && !hasAction(view, "play_recording"),
        "Losing lesson support blocked the safety Off action or allowed a new recording");

    state["telemetry"]["ghost_practice_support"]["supported"] = true;
    state["telemetry"]["ghost_practice"]["enabled"] = false;
    state["session"]["kind"] = "career";
    require(layout.open(scope, state), "Career pause did not open");
    view = layout.view(scope, state);
    require(!hasAction(view, "ghost_control") && !hasAction(view, "play_recording"),
        "Career fixture offered ghost control or recording load");

    state["session"]["kind"] = "training";
    auto results = scope;
    results.surface = NativeMenuSurface::Results;
    ++results.generation;
    require(layout.open(results, state), "Training results scope did not open");
    view = layout.view(results, state);
    require(!hasAction(view, "ghost_control") && !hasAction(view, "play_recording"),
        "Results surface offered live training ghost controls");
}

static void runTests() {
    selectedRecordingUsesOnlyTheSavedId();
    recordingScanKeepsTheNewestSixtyFourAttempts();
    toggleIsSupportedAvailableAndToggleOnly();
    unsupportedAndNonTrainingActivitiesHidePracticeControls();
}

int main() {
    try {
        runTests();
        std::cout << "Native ghost practice layout and action gates passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
