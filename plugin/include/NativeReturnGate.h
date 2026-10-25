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
    bool paused = false;
    bool frontendReady = false;
    bool frontendRoot = false;
};

// Pure one-shot gate. Only a successfully sent native Return command may arm
// it. Service JSON confirms persistence; it never supplies engine commands.
class NativeReturnGate {
public:
    bool arm(const std::string& nonce, const Json& payload, const std::string& intent) {
        if (nonce.empty() || !payload.is_object() || payload.size() != 3 ||
            !payload.contains("expected_session_id") || !payload["expected_session_id"].is_string() ||
            !payload.contains("expected_fixture_id") || !payload["expected_fixture_id"].is_string() ||
            !payload.contains("abandon") || !payload["abandon"].is_boolean()) return false;
        const auto activity = payload["expected_session_id"].get<std::string>();
        const auto fixture = payload["expected_fixture_id"].get<std::string>();
        if (activity.empty() || activity.size() > 128 || fixture.size() > 128 || !validIntent(intent)) return false;
        // Repeated clicks cannot re-arm an already issued return for this activity.
        if (nonce == nonce_ && activity == activity_ && fixture == fixture_) return true;
        if (pending()) return false;
        nonce_ = nonce;
        activity_ = activity;
        fixture_ = fixture;
        intent_ = intent;
        ready_ = false;
        issued_ = false;
        reopenAttempted_ = false;
        return true;
    }

    bool poll(const NativeReturnContext& context, const Json& state) {
        ready_ = false;
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
        ready_ = durable(state);
        if (!ready_) return false;
        // A title screen and map transition are both outside the match. Only a
        // current authored hub handshake plus the stock root stack completes it.
        if (!context.inGame) {
            if (context.frontendReady && context.frontendRoot) clear();
            return false;
        }
        return !issued_ && context.matchAvailable;
    }

    Json authorization(bool currentMovieReady, const std::string& surface) const {
        if (!ready_ || issued_ || !currentMovieReady || (surface != "pause" && surface != "results"))
            return Json::object();
        return {{"intent", intent_}, {"activity", activity_}, {"fixture", fixture_}};
    }

    // The host calls this from the validated native log callback before the
    // movie invokes its fixed typed shell route. It is an attempt, not arrival.
    bool markIssued(const std::string& nonce, const Json& state) {
        if (nonce != nonce_ || !pending() || !ready_ || issued_ || !durable(state)) return false;
        issued_ = true;
        return true;
    }

    bool takeReopenAttempt(const NativeReturnContext& context) {
        if (!ready_ || issued_ || reopenAttempted_ || !context.inGame || context.paused ||
            !context.matchAvailable || !context.fresh || context.nonce != nonce_) return false;
        reopenAttempted_ = true; // Before the void SDK call, including exceptions.
        return true;
    }

    static bool permitsAction(const std::string& action) {
        return action == "return_hub" || action == "retry_result_save" || action == "quit_game";
    }

    void clear() {
        nonce_.clear(); activity_.clear(); fixture_.clear(); intent_.clear();
        ready_ = false; issued_ = false; reopenAttempted_ = false;
    }
    bool pending() const { return !activity_.empty(); }
    bool issued() const { return issued_; }
    bool ready() const { return ready_; }
    bool reopenAttempted() const { return reopenAttempted_; }
    bool matchesNonce(const std::string& nonce) const { return !pending() || nonce == nonce_; }

private:
    bool durable(const Json& state) const {
        if (!state.is_object() || stringValue(state, "bridge_session") != nonce_) return false;
        const auto session = objectValue(state, "session");
        const auto activeId = stringValue(session, "id");
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
        return true;
    }
    static bool validIntent(const std::string& value) {
        if (value.size() != 32) return false;
        for (const auto c : value) if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
        return true;
    }
    static bool explicitFalse(const Json& value, const char* name) {
        return value.contains(name) && value[name].is_boolean() && !value[name].get<bool>();
    }
    std::string nonce_;
    std::string activity_;
    std::string fixture_;
    std::string intent_;
    bool ready_ = false;
    bool issued_ = false;
    bool reopenAttempted_ = false;
};
}
