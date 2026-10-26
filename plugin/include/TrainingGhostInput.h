#pragma once

// Pure, platform-free edge processing for the offline Training ghost toggle.
//
// The host samples one XInput controller each existing tick and hands the
// observation here. This header deliberately depends only on nlohmann/json and
// the C++ standard library so it can be unit tested without Windows, BakkesMod
// or a game process.
//
// Contract:
//  * Observe only. Nothing here binds, consumes or replaces a Rocket League
//    control and nothing here sends vehicle input.
//  * Exactly one connected controller slot is required. Zero or several
//    connected slots produce no toggle.
//  * The button edge is sampled on every tick, before any eligibility test, so
//    a button held across a career/training, pause/resume, focus or session
//    transition can never become a new press.
//  * A release is required before an eligible press after startup, a new
//    controller slot, a new session identity or a disabled scope.
//  * A short local latch suppresses duplicate commands until the observed
//    pending flag clears, the observed enabled state changes, or the deadline
//    expires.

#include <nlohmann/json.hpp>

#include <cstdint>
#include <string>

namespace mct {

class TrainingGhostInput {
public:
    using Json = nlohmann::json;

    // Host-supplied observation of the owned game. The host owns every one of
    // these facts; bridge JSON cannot choose them.
    struct Scope {
        bool owned = false;              // owned fresh offline session
        bool fresh = false;              // bridge state is fresh
        bool foreground = false;         // foreground window pid == this process
        bool inGame = false;             // actual in-game, not frontend
        bool online = true;              // fail closed
        bool replay = false;
        bool paused = false;
        bool matchEnded = false;
        bool nativeMenuActive = false;   // native menu active or in menus
        bool referenceCaptureActive = false;
    };

    // slot is the single connected XInput slot, or -1 when zero or several
    // controllers are connected. dpadLeft is the observed button bit.
    struct Pad {
        int slot = -1;
        bool dpadLeft = false;
    };

    struct Decision {
        bool toggle = false;
        bool enabled = false;
        std::string session;
        std::string lesson;
    };

    static constexpr double kLatchSeconds = 5.0;

    Decision observe(const Scope& scope, const Json& state, const Pad& pad, double now) {
        Decision out;
        const auto session = object(state, "session");
        const auto telemetry = object(state, "telemetry");
        const auto practice = object(telemetry, "ghost_practice");
        const auto support = object(telemetry, "ghost_practice_support");
        const bool enabled = boolean(practice, "enabled", false);
        const bool pending = pendingFlag(telemetry);
        const std::string sessionId = text(session, "id");
        const std::string lesson = text(telemetry, "lesson_id");
        const std::string identity = text(state, "bridge_session") + "|" + sessionId + "|" + lesson;

        // A new or lost controller slot always needs a fresh release.
        if (pad.slot != slot_) {
            slot_ = pad.slot;
            held_ = pad.dpadLeft;
            armed_ = false;
            clearLatch();
            identity_.clear();
        }
        if (pad.slot < 0) {
            held_ = false;
            armed_ = false;
            clearLatch();
            identity_.clear();
            return out;
        }
        // Explicit session identity reset: a different bridge session, activity
        // or lesson is a different scope and needs a fresh release.
        if (identity != identity_) {
            identity_ = identity;
            held_ = pad.dpadLeft;
            armed_ = false;
            clearLatch();
        }

        // Edge state is sampled on every tick, before any eligibility test.
        const bool pressed = pad.dpadLeft && !held_;
        held_ = pad.dpadLeft;
        const bool scopeOk = eligible(scope, state, session, practice, support, enabled, pending, lesson);
        // A disabled scope disarms: the player must release before an eligible
        // press can toggle, so a button held across a pause, focus loss or
        // session change never fires.
        if (!pad.dpadLeft) armed_ = true;
        else if (!scopeOk) armed_ = false;

        if (latch_) {
            if (pending) latchSawPending_ = true;
            const bool cleared = (latchSawPending_ && !pending) || enabled != latchEnabled_ ||
                now >= latchDeadline_ || now < latchStart_;
            if (cleared) clearLatch();
        }
        if (!pressed || !armed_ || !scopeOk || latch_) return out;

        latch_ = true;
        latchStart_ = now;
        latchDeadline_ = now + kLatchSeconds;
        latchEnabled_ = enabled;
        latchSawPending_ = pending;
        out.toggle = true;
        out.enabled = !enabled;
        out.session = sessionId;
        out.lesson = lesson;
        return out;
    }

    // Explicit reset for unload, offline loss or a host-side scope change.
    void reset() {
        slot_ = -1;
        held_ = false;
        armed_ = false;
        clearLatch();
        identity_.clear();
    }

    int slot() const { return slot_; }
    bool held() const { return held_; }
    bool armed() const { return armed_; }
    bool latched() const { return latch_; }
    const std::string& identity() const { return identity_; }

    // True only when the observed state allows turning the ghost on or off.
    static bool eligible(const Scope& scope, const Json& state, const Json& session, const Json& practice,
                         const Json& support, bool enabled, bool pending, const std::string& lesson) {
        if (!scope.owned || !scope.fresh || !scope.foreground || !scope.inGame) return false;
        if (scope.online || scope.replay || scope.paused || scope.matchEnded) return false;
        if (scope.nativeMenuActive || scope.referenceCaptureActive) return false;
        if (!boolean(state, "offline", false)) return false;
        // A toggle is bound to one identified bridge session and activity.
        if (text(state, "bridge_session").empty()) return false;
        if (text(session, "id").empty()) return false;
        if (text(session, "kind") != "training") return false;
        if (text(session, "state") != "training") return false;
        if (!boolean(session, "worker_running", false)) return false;
        if (boolean(session, "busy", true)) return false;
        if (lesson.empty()) return false;
        if (pending) return false;
        // Support lost while the ghost is on still allows turning it off.
        const bool supported = boolean(support, "supported", false);
        const bool available = boolean(practice, "available", false);
        return enabled || (supported && available);
    }

    // Agreed contract: telemetry.ghost_practice_pending is a boolean flag. A
    // non-empty object is also treated as pending so an older publisher cannot
    // unlock a second edge.
    static bool pendingFlag(const Json& telemetry) {
        if (!telemetry.is_object() || !telemetry.contains("ghost_practice_pending")) return false;
        const auto& value = telemetry["ghost_practice_pending"];
        if (value.is_boolean()) return value.get<bool>();
        return value.is_object() && !value.empty();
    }

private:
    void clearLatch() {
        latch_ = false;
        latchStart_ = 0.0;
        latchDeadline_ = 0.0;
        latchEnabled_ = false;
        latchSawPending_ = false;
    }

    static Json object(const Json& value, const char* key) {
        if (!value.is_object() || !value.contains(key)) return Json::object();
        const auto& child = value[key];
        return child.is_object() ? child : Json::object();
    }

    static std::string text(const Json& value, const char* key) {
        if (!value.is_object() || !value.contains(key)) return std::string();
        const auto& child = value[key];
        return child.is_string() ? child.get<std::string>() : std::string();
    }

    static bool boolean(const Json& value, const char* key, bool fallback) {
        if (!value.is_object() || !value.contains(key)) return fallback;
        const auto& child = value[key];
        return child.is_boolean() ? child.get<bool>() : fallback;
    }

    int slot_ = -1;
    bool held_ = false;
    bool armed_ = false;
    bool latch_ = false;
    double latchStart_ = 0.0;
    double latchDeadline_ = 0.0;
    bool latchEnabled_ = false;
    bool latchSawPending_ = false;
    std::string identity_;
};

}  // namespace mct
