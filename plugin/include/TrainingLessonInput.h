#pragma once

// Pure lesson-control state, scoped BakkesMod binding restoration, and the
// small data/layout model used by the in-game training HUD.

#include <nlohmann/json.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <functional>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>

namespace mct {

class TrainingLessonInput {
public:
    using Json = nlohmann::json;

    enum class Action { None, Previous, Next, ToggleGhost, Retry };

    struct Scope {
        bool owned = false;
        bool fresh = false;
        bool foreground = false;
        bool inGame = false;
        bool online = true;
        bool replay = false;
        bool paused = false;
        bool matchEnded = false;
        bool nativeMenuActive = false;
        bool referenceCaptureActive = false;
    };

    struct Pad {
        // The host can identify XInput slots. -2 is the SDK's logical gamepad
        // path (including controllers which are not exposed through XInput),
        // and -1 means that no unambiguous input source is available.
        int slot = -1;
        bool left = false;
        bool right = false;
        bool up = false;
        bool down = false;
    };

    struct Decision {
        Action action = Action::None;
        bool ghostEnabled = false;
    };

    static constexpr double kLatchSeconds = 5.0;

    Decision observe(const Scope& scope, const Json& state, const Pad& pad, double now) {
        const auto session = object(state, "session");
        const auto telemetry = object(state, "telemetry");
        const auto coaching = object(telemetry, "coaching");
        const auto practice = object(telemetry, "ghost_practice");
        const auto support = object(telemetry, "ghost_practice_support");
        const std::string identity = text(state, "bridge_session") + "|" +
            text(session, "id") + "|" + text(telemetry, "lesson_id");
        const std::array<bool, 4> down{{pad.left, pad.right, pad.up, pad.down}};
        const bool scopeOk = lessonScope(scope, state);

        if (pad.slot != slot_ || identity != identity_) {
            slot_ = pad.slot;
            identity_ = identity;
            held_ = down;
            armed_.fill(false);
            scopeWasEligible_ = false;
            clearLatch();
        }
        if (pad.slot == -1) {
            held_.fill(false);
            armed_.fill(false);
            scopeWasEligible_ = false;
            clearLatch();
            identity_.clear();
            return {};
        }

        if (!scopeOk) {
            held_ = down;
            armed_.fill(false);
            scopeWasEligible_ = false;
            return {};
        }
        if (!scopeWasEligible_) {
            held_ = down;
            for (std::size_t index = 0; index < down.size(); ++index) armed_[index] = !down[index];
            scopeWasEligible_ = true;
            return {};
        }

        std::array<bool, 4> pressed{};
        for (std::size_t index = 0; index < down.size(); ++index) {
            pressed[index] = down[index] && !held_[index] && armed_[index];
            held_[index] = down[index];
            if (!down[index]) armed_[index] = true;
        }

        const bool busy = boolean(session, "busy", true);
        const bool ghostPending = pendingFlag(telemetry);
        const bool ghostEnabled = boolean(practice, "enabled", false);
        const int scenario = positiveInteger(coaching, "scenario_index");
        const std::string phase = text(coaching, "phase");
        if (latched_) {
            if (ghostPending) latchSawGhostPending_ = true;
            const auto commandAck = object(state, "command_ack");
            const bool rejected = !latchCommandId_.empty() && text(commandAck, "id") == latchCommandId_ &&
                commandAck.contains("ok") && commandAck["ok"].is_boolean() && !commandAck["ok"].get<bool>();
            const bool scenarioAck = (latchedAction_ == Action::Previous || latchedAction_ == Action::Next) &&
                scenario > 0 && latchScenario_ > 0 && scenario != latchScenario_;
            const bool ghostAck = latchedAction_ == Action::ToggleGhost &&
                (ghostEnabled != latchGhostEnabled_ || (latchSawGhostPending_ && !ghostPending));
            const auto attempt = text(coaching, "attempt_id");
            const bool retryAck = latchedAction_ == Action::Retry && !latchAttempt_.empty() &&
                !attempt.empty() && attempt != latchAttempt_;
            if (rejected || scenarioAck || ghostAck || retryAck || now >= latchDeadline_ || now < latchStarted_)
                clearLatch();
        }
        if (busy || latched_) return {};

        Action action = Action::None;
        if (pressed[0]) action = Action::Previous;
        else if (pressed[1]) action = Action::Next;
        else if (pressed[2]) action = Action::Retry;
        else if (pressed[3] && ghostToggleAvailable(practice, support, ghostPending)) action = Action::ToggleGhost;
        if (action == Action::None) return {};

        latched_ = true;
        latchedAction_ = action;
        latchStarted_ = now;
        latchDeadline_ = now + kLatchSeconds;
        latchScenario_ = scenario;
        latchGhostEnabled_ = ghostEnabled;
        latchPhase_ = phase;
        latchAttempt_ = text(coaching, "attempt_id");
        latchSawGhostPending_ = ghostPending;
        return {action, action == Action::ToggleGhost ? !ghostEnabled : false};
    }

    void commandSent(std::string id) {
        if (latched_) latchCommandId_ = std::move(id);
    }

    void commandFailed() { clearLatch(); }

    void reset() {
        slot_ = -1;
        held_.fill(false);
        armed_.fill(false);
        scopeWasEligible_ = false;
        identity_.clear();
        clearLatch();
    }

    bool latched() const { return latched_; }

    static bool lessonScope(const Scope& scope, const Json& state) {
        if (!scope.owned || !scope.fresh || !scope.foreground || !scope.inGame) return false;
        if (scope.online || scope.replay || scope.paused || scope.matchEnded) return false;
        if (scope.nativeMenuActive || scope.referenceCaptureActive) return false;
        if (!boolean(state, "offline", false) || text(state, "bridge_session").empty()) return false;
        const auto session = object(state, "session");
        const auto telemetry = object(state, "telemetry");
        return !text(session, "id").empty() && text(session, "kind") == "training" &&
            text(session, "state") == "training" && boolean(session, "worker_running", false) &&
            text(telemetry, "lesson_id") == "power-shots";
    }

    static bool ghostAvailable(const Json& state) {
        const auto telemetry = object(state, "telemetry");
        const auto practice = object(telemetry, "ghost_practice");
        const auto support = object(telemetry, "ghost_practice_support");
        return boolean(practice, "enabled", false) ||
            (boolean(support, "supported", false) && boolean(practice, "available", false));
    }

    static bool ghostEnabled(const Json& state) {
        return boolean(object(object(state, "telemetry"), "ghost_practice"), "enabled", false);
    }

private:
    static bool ghostToggleAvailable(const Json& practice, const Json& support, bool pending) {
        if (pending) return false;
        return boolean(practice, "enabled", false) ||
            (boolean(support, "supported", false) && boolean(practice, "available", false));
    }

    static bool pendingFlag(const Json& telemetry) {
        if (!telemetry.is_object() || !telemetry.contains("ghost_practice_pending")) return false;
        const auto& value = telemetry["ghost_practice_pending"];
        if (value.is_boolean()) return value.get<bool>();
        return value.is_object() && !value.empty();
    }

    static Json object(const Json& value, const char* key) {
        if (!value.is_object() || !value.contains(key) || !value[key].is_object()) return Json::object();
        return value[key];
    }

    static std::string text(const Json& value, const char* key) {
        if (!value.is_object() || !value.contains(key) || !value[key].is_string()) return {};
        return value[key].get<std::string>();
    }

    static bool boolean(const Json& value, const char* key, bool fallback) {
        if (!value.is_object() || !value.contains(key) || !value[key].is_boolean()) return fallback;
        return value[key].get<bool>();
    }

    static int positiveInteger(const Json& value, const char* key) {
        if (!value.is_object() || !value.contains(key)) return 0;
        const auto& number = value[key];
        if (number.is_number_unsigned()) {
            const auto raw = number.get<std::uint64_t>();
            return raw > 0 && raw <= 1000 ? static_cast<int>(raw) : 0;
        }
        if (!number.is_number_integer()) return 0;
        const auto raw = number.get<std::int64_t>();
        return raw > 0 && raw <= 1000 ? static_cast<int>(raw) : 0;
    }

    void clearLatch() {
        latched_ = false;
        latchedAction_ = Action::None;
        latchStarted_ = 0;
        latchDeadline_ = 0;
        latchScenario_ = 0;
        latchGhostEnabled_ = false;
        latchPhase_.clear();
        latchAttempt_.clear();
        latchCommandId_.clear();
        latchSawGhostPending_ = false;
    }

    int slot_ = -1;
    std::array<bool, 4> held_{};
    std::array<bool, 4> armed_{};
    bool scopeWasEligible_ = false;
    std::string identity_;
    bool latched_ = false;
    Action latchedAction_ = Action::None;
    double latchStarted_ = 0;
    double latchDeadline_ = 0;
    int latchScenario_ = 0;
    bool latchGhostEnabled_ = false;
    std::string latchPhase_;
    std::string latchAttempt_;
    std::string latchCommandId_;
    bool latchSawGhostPending_ = false;
};

class TrainingBindingGuard {
public:
    static constexpr std::array<const char*, 4> keys{{
        "XboxTypeS_DPad_Left", "XboxTypeS_DPad_Right", "XboxTypeS_DPad_Up", "XboxTypeS_DPad_Down"}};
    static constexpr std::array<const char*, 4> commands{{
        "mct_training_previous", "mct_training_next", "mct_training_retry", "mct_training_ghost"}};

    using Read = std::function<std::string(const std::string&)>;
    using Write = std::function<void(const std::string&, const std::string&)>;
    using Remove = std::function<void(const std::string&)>;

    bool acquire(const Read& read, const Write& write, const Remove& remove) {
        if (active_) return true;
        if (restorePending_) {
            if (!restore(read, write, remove)) return false;
            restorePending_ = false;
            previous_.fill({});
        }
        try {
            for (std::size_t index = 0; index < keys.size(); ++index) previous_[index] = read(keys[index]);
        } catch (...) {
            previous_.fill({});
            return false;
        }
        restorePending_ = true;
        try {
            for (std::size_t index = 0; index < keys.size(); ++index) write(keys[index], commands[index]);
            for (std::size_t index = 0; index < keys.size(); ++index)
                if (read(keys[index]) != commands[index]) throw std::runtime_error("Binding write was not retained.");
        } catch (...) {
            if (restore(read, write, remove)) {
                restorePending_ = false;
                previous_.fill({});
            }
            return false;
        }
        active_ = true;
        restorePending_ = false;
        return true;
    }

    bool release(const Read& read, const Write& write, const Remove& remove) {
        if (!active_ && !restorePending_) return true;
        active_ = false;
        restorePending_ = true;
        if (!restore(read, write, remove)) return false;
        restorePending_ = false;
        previous_.fill({});
        return true;
    }

    bool active() const { return active_; }

private:
    bool restore(const Read& read, const Write& write, const Remove& remove) {
        bool restored = true;
        for (std::size_t index = 0; index < keys.size(); ++index) {
            try {
                if (read(keys[index]) != commands[index]) continue;
                if (previous_[index].empty()) remove(keys[index]);
                else write(keys[index], previous_[index]);
                if (read(keys[index]) != previous_[index]) restored = false;
            } catch (...) {
                restored = false;
            }
        }
        return restored;
    }

    bool active_ = false;
    bool restorePending_ = false;
    std::array<std::string, 4> previous_{};
};

struct TrainingHudModel {
    using Json = nlohmann::json;
    bool active = false;
    bool powerShots = false;
    bool scenarioKnown = false;
    int scenarioIndex = 0;
    int scenarioTotal = 0;
    std::string title;
    std::string rank;
    std::string phase;
    bool timerKnown = false;
    double timeLimit = 0;
    double timeRemaining = 0;
    std::string countdown;
    bool ghostAvailable = false;
    bool ghostEnabled = false;

    static TrainingHudModel fromState(const Json& state) {
        TrainingHudModel out;
        const auto session = child(state, "session");
        const auto telemetry = child(state, "telemetry");
        const auto coaching = child(telemetry, "coaching");
        const auto lessonId = safeText(telemetry, "lesson_id");
        out.active = safeText(session, "kind") == "training" && safeText(session, "state") == "training" &&
            flag(session, "worker_running", false) && !lessonId.empty();
        out.powerShots = lessonId == "power-shots";
        if (!out.active) return out;

        out.scenarioIndex = integer(coaching, "scenario_index");
        out.scenarioTotal = integer(coaching, "scenario_total");
        out.scenarioKnown = out.scenarioIndex > 0 && out.scenarioTotal > 0 && out.scenarioIndex <= out.scenarioTotal;
        if (!out.scenarioKnown) { out.scenarioIndex = 0; out.scenarioTotal = 0; }
        out.title = safeText(coaching, "scenario_title");
        if (out.title.empty()) out.title = safeText(telemetry, "lesson_title");
        if (out.title.empty()) {
            for (const auto& lesson : array(state, "lessons"))
                if (safeText(lesson, "id") == lessonId) { out.title = safeText(lesson, "title"); break; }
        }
        if (out.title.empty()) {
            const auto selected = child(state, "selected_lesson");
            if (safeText(selected, "id").empty() || safeText(selected, "id") == lessonId)
                out.title = safeText(selected, "title");
        }
        if (out.title.empty()) out.title = lessonId;
        out.rank = safeText(coaching, "rank_title");
        out.phase = safeText(coaching, "phase");

        const double limit = finiteNumber(coaching, "time_limit_seconds");
        const double remaining = finiteNumber(coaching, "time_remaining_seconds");
        if (limit > 0 && remaining >= 0) {
            out.timerKnown = true;
            out.timeLimit = std::min(limit, 3600.0);
            out.timeRemaining = std::clamp(remaining, 0.0, out.timeLimit);
        }
        const auto countdown = safeText(coaching, "countdown");
        if (countdown == "SETTLE" || countdown == "READY" || countdown == "GO") out.countdown = countdown;
        out.ghostAvailable = TrainingLessonInput::ghostAvailable(state);
        out.ghostEnabled = TrainingLessonInput::ghostEnabled(state);
        return out;
    }

private:
    static Json child(const Json& value, const char* key) {
        if (!value.is_object() || !value.contains(key) || !value[key].is_object()) return Json::object();
        return value[key];
    }
    static Json array(const Json& value, const char* key) {
        if (!value.is_object() || !value.contains(key) || !value[key].is_array()) return Json::array();
        return value[key];
    }
    static std::string safeText(const Json& value, const char* key) {
        if (!value.is_object() || !value.contains(key) || !value[key].is_string()) return {};
        std::string text = value[key].get<std::string>();
        if (text.size() > 80) {
            std::size_t limit = 80;
            while (limit > 0 && (static_cast<unsigned char>(text[limit]) & 0xc0) == 0x80) --limit;
            text.resize(limit);
        }
        for (char& character : text) if (static_cast<unsigned char>(character) < 32) character = ' ';
        return text;
    }
    static bool flag(const Json& value, const char* key, bool fallback) {
        if (!value.is_object() || !value.contains(key) || !value[key].is_boolean()) return fallback;
        return value[key].get<bool>();
    }
    static int integer(const Json& value, const char* key) {
        if (!value.is_object() || !value.contains(key)) return 0;
        const auto& number = value[key];
        if (number.is_number_unsigned()) {
            const auto raw = number.get<std::uint64_t>();
            return raw > 0 && raw <= 1000 ? static_cast<int>(raw) : 0;
        }
        if (!number.is_number_integer()) return 0;
        const auto raw = number.get<std::int64_t>();
        return raw > 0 && raw <= 1000 ? static_cast<int>(raw) : 0;
    }
    static double finiteNumber(const Json& value, const char* key) {
        if (!value.is_object() || !value.contains(key) || !value[key].is_number()) return -1;
        const double number = value[key].get<double>();
        return std::isfinite(number) ? number : -1;
    }
};

struct TrainingHudLayout {
    float margin = 18;
    float leftWidth = 390;
    float cardTop = 54;
    float cardHeight = 142;
    float rightHintX = 0;
    float rightHintWidth = 172;

    static TrainingHudLayout forScreen(float width, float height) {
        TrainingHudLayout out;
        out.margin = width < 1500 ? 14.0f : 18.0f;
        out.leftWidth = std::max(280.0f, std::min(390.0f, width * 0.46f));
        out.cardTop = height < 900 ? 48.0f : 54.0f;
        out.cardHeight = height < 900 ? 132.0f : 142.0f;
        out.rightHintWidth = width < 1500 ? 158.0f : 172.0f;
        out.rightHintX = std::max(out.margin, width - out.margin - out.rightHintWidth);
        return out;
    }

    bool fits(float width, float height) const {
        return margin >= 0 && margin + leftWidth <= width && rightHintX >= 0 &&
            rightHintX + rightHintWidth <= width && cardTop + cardHeight <= height * 0.45f;
    }
};

}  // namespace mct
