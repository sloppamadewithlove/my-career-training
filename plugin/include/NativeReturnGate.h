#pragma once

#include "LocalBridge.h"

namespace mct {

struct NativeReturnContext {
    std::string nonce;
    bool owned = false;
    bool fresh = false;
    bool offline = false;
    bool online = true;
    bool replay = true;
    bool buildVerified = false;
    bool inGame = false;
    bool matchAvailable = false;
};

// Pure one-shot gate. Only a successfully sent native Return command may arm
// it. Service JSON confirms persistence; it never supplies engine commands.
class NativeReturnGate {
public:
    bool arm(const std::string& nonce, const Json& payload) {
        if (nonce.empty() || !payload.is_object() || payload.size() != 3 ||
            !payload.contains("expected_session_id") || !payload["expected_session_id"].is_string() ||
            !payload.contains("expected_fixture_id") || !payload["expected_fixture_id"].is_string() ||
            !payload.contains("abandon") || !payload["abandon"].is_boolean()) return false;
        const auto activity = payload["expected_session_id"].get<std::string>();
        const auto fixture = payload["expected_fixture_id"].get<std::string>();
        if (activity.empty() || activity.size() > 128 || fixture.size() > 128) return false;
        // Repeated clicks cannot re-arm an already issued return for this activity.
        if (nonce == nonce_ && activity == activity_ && fixture == fixture_) return true;
        nonce_ = nonce;
        activity_ = activity;
        fixture_ = fixture;
        issued_ = false;
        return true;
    }

    bool poll(const NativeReturnContext& context, const Json& state) {
        // Stale data cannot authorize navigation, but a temporary IPC delay
        // must not forget a command already issued in the same owned scope.
        if (!context.fresh && context.owned && context.offline && !context.online && !context.replay &&
            context.buildVerified && context.nonce == nonce_) return false;
        if (!context.owned || !context.fresh || !context.offline || context.online || context.replay ||
            !context.buildVerified || context.nonce.empty() || !state.is_object() ||
            !state.contains("protocol") || !state["protocol"].is_number_integer() || state["protocol"] != 1 ||
            !state.contains("offline") || !state["offline"].is_boolean() || !state["offline"].get<bool>() ||
            stringValue(state, "bridge_session") != context.nonce || context.nonce != nonce_) {
            clear();
            return false;
        }
        if (activity_.empty()) return false;
        const auto session = objectValue(state, "session");
        const auto activeId = stringValue(session, "id");
        if (!activeId.empty() && (activeId != activity_ || stringValue(session, "fixture_id") != fixture_)) {
            clear(); return false;
        }
        if (!context.inGame) { clear(); return false; }
        if (issued_ || !context.matchAvailable) return false;
        const auto ready = objectValue(state, "native_return_ready");
        if (ready.size() != 2 || stringValue(ready, "session_id") != activity_ ||
            !ready.contains("fixture_id") || !ready["fixture_id"].is_string() ||
            ready["fixture_id"].get<std::string>() != fixture_) return false;
        if (!session.contains("id") || (!session["id"].is_null() && !session["id"].is_string()) || !activeId.empty() ||
            !session.contains("fixture_id") || !session["fixture_id"].is_null() ||
            stringValue(session, "state") != "Idle" ||
            stringValue(session, "kind") != "hub" ||
            !explicitFalse(session, "worker_running") || !explicitFalse(session, "busy") ||
            !state.contains("error") || !state["error"].is_string() || !state["error"].get<std::string>().empty())
            return false;
        if (!state.contains("career") || (!state["career"].is_null() && !state["career"].is_object())) return false;
        const auto career = objectValue(state, "career");
        if (career.contains("pending_session") && !career["pending_session"].is_null()) return false;
        issued_ = true; // Before the SDK call, including a throwing/reentrant call.
        return true;
    }

    void clear() { nonce_.clear(); activity_.clear(); fixture_.clear(); issued_ = false; }
    bool pending() const { return !activity_.empty(); }
    bool issued() const { return issued_; }
    bool matchesNonce(const std::string& nonce) const { return !pending() || nonce == nonce_; }

private:
    static bool explicitFalse(const Json& value, const char* name) {
        return value.contains(name) && value[name].is_boolean() && !value[name].get<bool>();
    }
    std::string nonce_;
    std::string activity_;
    std::string fixture_;
    bool issued_ = false;
};
}
