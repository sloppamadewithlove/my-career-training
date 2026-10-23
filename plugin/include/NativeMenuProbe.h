#pragma once

#include "LocalBridge.h"

#include <cmath>
#include <cstddef>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

namespace mct {

// Values supplied by the existing owned-session check. A hook must never
// infer ownership from a menu name, a game mode, or an event callback alone.
struct NativeProbeScope {
    bool owned = false;
    bool fresh = false;
    bool online = true;
    std::string sessionNonce;
    std::string gameBuild;
    std::string executableSha256; // Empty until the exact executable is hashed.
    std::string bakkesVersion;
};

// Diagnostic only: stores menu *names* and occurrence of named functions.
// It never reads hook parameters, follows Unreal pointers, or mutates a menu.
class NativeMenuProbe {
public:
    static constexpr std::size_t kMaxEvents = 1000;
    static constexpr double kMaxSeconds = 120.0;
    static constexpr const char* kOutputName = "native-menu-probe.json";

    bool start(const NativeProbeScope& scope, double now) {
        std::lock_guard<std::mutex> lock(mutex_);
        clearLocked();
        if (!safeScope(scope) || !std::isfinite(now) || now < 0.0) return false;
        nonce_ = scope.sessionNonce;
        build_ = scope.gameBuild;
        executableSha256_ = validSha256(scope.executableSha256) ? scope.executableSha256 : "";
        bakkesVersion_ = safeIdentifier(scope.bakkesVersion, 64) ? scope.bakkesVersion : "";
        startedAt_ = now;
        active_ = true;
        return true;
    }

    // Return true only when an allowlisted observation was recorded. An unsafe
    // transition destroys the entire trace immediately, even after a limit was
    // reached. The caller should invoke this on each tick and hooked event.
    bool observe(const NativeProbeScope& scope, const std::string& eventName,
                 const std::string& topMenu, bool inGame, double now) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!safeCurrentScope(scope) || !std::isfinite(now) || now < startedAt_) {
            clearLocked();
            return false;
        }
        if (!active_) return false;
        if (now - startedAt_ >= kMaxSeconds) {
            active_ = false;
            finishReason_ = "duration_limit";
            return false;
        }
        if (!allowedEvent(eventName) || !safeIdentifier(topMenu, 128)) return false;
        events_.push_back({{"time", now}, {"event", eventName},
                           {"top_menu", topMenu}, {"in_game", inGame},
                           {"online", false}});
        if (events_.size() >= kMaxEvents) {
            active_ = false;
            finishReason_ = "event_limit";
        }
        return true;
    }

    // Stop is the only operation that writes a trace. The destination is a
    // fixed basename under the bridge's per-user directory, never input data.
    bool stopToBridge(const NativeProbeScope& scope, double now, LocalBridge& bridge) {
        Json trace;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (!safeCurrentScope(scope) || !std::isfinite(now) || now < startedAt_) {
                clearLocked();
                return false;
            }
            trace = {{"schema_version", 1}, {"kind", "native_menu_read_only_probe"},
                     {"started_at", startedAt_}, {"finished_at", now},
                     {"scope", {{"bridge_session", nonce_}, {"game_build", build_},
                                {"executable_sha256", executableSha256_.empty() ? Json(nullptr) : Json(executableSha256_)},
                                {"bakkesmod_version", bakkesVersion_},
                                {"owned_offline_session", true}}},
                     {"limits", {{"duration_seconds", kMaxSeconds}, {"event_count", kMaxEvents}}},
                     {"finish_reason", finishReason_.empty() ? "operator_stop" : finishReason_},
                     {"native_mutations", false}, {"events", events_}};
            clearLocked();
        }
        LocalBridge::atomicWrite(bridge.directory() / kOutputName, trace.dump(2));
        return true;
    }

    void clear() {
        std::lock_guard<std::mutex> lock(mutex_);
        clearLocked();
    }

    bool active() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return active_;
    }

    // A duration-limited trace can have zero events. Continue checking its
    // scope on every tick until it is exported or erased.
    bool hasTrace() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return !nonce_.empty();
    }

    std::size_t eventCount() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return events_.size();
    }

    static bool allowedEvent(const std::string& name) {
        return name == "menu_stack_transition" ||
               name == "Function TAGame.GFxData_MenuStack_TA.ButtonTriggered" ||
               name == "Function TAGame.GFxData_MenuStack_TA.PushMenu" ||
               name == "Function TAGame.GFxData_MenuStack_TA.PopMenu" ||
               name == "Function TAGame.GFxData_MenuTree_TA.OnChildNodeClicked";
    }

private:
    static bool safeIdentifier(const std::string& value, std::size_t maximum) {
        if (value.size() > maximum) return false;
        for (const unsigned char character : value) {
            if (!((character >= 'A' && character <= 'Z') ||
                  (character >= 'a' && character <= 'z') ||
                  (character >= '0' && character <= '9') ||
                  character == '_' || character == '-' || character == '.' ||
                  character == '/' || character == '+' || character == ':' ||
                  character == ' ')) return false;
        }
        return true;
    }

    static bool validSha256(const std::string& value) {
        if (value.size() != 64) return false;
        for (const unsigned char character : value)
            if (!((character >= '0' && character <= '9') ||
                  (character >= 'a' && character <= 'f'))) return false;
        return true;
    }

    static bool validNonce(const std::string& value) {
        if (value.size() != 36) return false;
        for (std::size_t index = 0; index < value.size(); ++index) {
            if (index == 8 || index == 13 || index == 18 || index == 23) {
                if (value[index] != '-') return false;
            } else if (!((value[index] >= '0' && value[index] <= '9') ||
                         (value[index] >= 'a' && value[index] <= 'f'))) return false;
        }
        return true;
    }

    static bool safeScope(const NativeProbeScope& scope) {
        return scope.owned && scope.fresh && !scope.online &&
               validNonce(scope.sessionNonce) &&
               !scope.gameBuild.empty() && safeIdentifier(scope.gameBuild, 128);
    }

    bool safeCurrentScope(const NativeProbeScope& scope) const {
        return !nonce_.empty() && safeScope(scope) &&
               scope.sessionNonce == nonce_ && scope.gameBuild == build_;
    }

    void clearLocked() {
        active_ = false;
        startedAt_ = 0.0;
        nonce_.clear();
        build_.clear();
        executableSha256_.clear();
        bakkesVersion_.clear();
        finishReason_.clear();
        events_.clear();
    }

    mutable std::mutex mutex_;
    bool active_ = false;
    double startedAt_ = 0.0;
    std::string nonce_;
    std::string build_;
    std::string executableSha256_;
    std::string bakkesVersion_;
    std::string finishReason_;
    std::vector<Json> events_;
};

} // namespace mct
