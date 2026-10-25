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
    bool arm(const std::string& nonce, const Json& payload, const std::string& intent, double now = 0) {
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
        executeOffered_ = false;
        arrived_ = false;
        consumedGeneration_.clear();
        consumedSurface_.clear();
        holdStarted_ = now;
        return true;
    }

    bool poll(const NativeReturnContext& context, const Json& state) {
        if (!pending()) return false;
        ready_ = false;
        // Stale data cannot authorize navigation, but a temporary IPC delay
        // must not forget a command already issued in the same owned scope.
        if (!context.fresh && context.owned && context.offline && !context.online && !context.replay &&
            context.buildVerified && context.nonce == nonce_) { suspendExecution(); return false; }
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
        if (!ready_) { suspendExecution(); return false; }
        // A title screen and map transition are both outside the match. Only a
        // current authored hub handshake plus the stock root stack completes it.
        if (!context.inGame) {
            if (context.frontendReady && context.frontendRoot) {
                nonce_.clear(); activity_.clear(); fixture_.clear(); intent_.clear();
                ready_ = false; consumedGeneration_.clear(); consumedSurface_.clear();
                arrived_ = true;
            }
            return false;
        }
        return !issued_ && context.matchAvailable;
    }

    Json authorization(bool currentMovieReady, const std::string& surface) const {
        if (!ready_ || issued_ || !currentMovieReady || (surface != "pause" && surface != "results"))
            return Json::object();
        if (executeOffered_ && (consumedGeneration_.empty() || consumedSurface_ != surface)) return Json::object();
        Json value = {{"phase", "authorize"}, {"intent", intent_}, {"activity", activity_}, {"fixture", fixture_}};
        if (!consumedGeneration_.empty() && consumedSurface_ == surface) {
            value["phase"] = "execute";
            value["consumed_generation"] = consumedGeneration_;
        }
        return value;
    }

    // A void native log cannot acknowledge acceptance to ActionScript. Only
    // a subsequent generation-bound execute view confirms this consumption.
    bool markConsumed(const NativeReturnContext& context, const Json& state,
                      const std::string& surface, const std::string& generation) {
        if (!safe(context) || !pending() || !ready_ || issued_ || !durable(state) ||
            (surface != "pause" && surface != "results") || !validGeneration(generation)) return false;
        if (!consumedGeneration_.empty())
            return consumedGeneration_ == generation && consumedSurface_ == surface;
        if (executeOffered_) return false;
        consumedGeneration_ = generation;
        consumedSurface_ = surface;
        return true;
    }

    // Set only after the host successfully writes an execute view. Delivery is
    // uncertain if its issued log is lost, so never offer another Shell attempt
    // after that movie unloads or its grant is withdrawn.
    bool noteExecutePublished(const std::string& surface, const std::string& generation) {
        if (!pending() || !ready_ || issued_ || consumedGeneration_.empty() ||
            consumedSurface_ != surface || consumedGeneration_ != generation) return false;
        executeOffered_ = true;
        return true;
    }

    bool markIssued(const NativeReturnContext& context, const Json& state,
                    const std::string& surface, const std::string& consumedGeneration) {
        if (!safe(context) || !pending() || !ready_ || issued_ || !executeOffered_ || !durable(state) ||
            consumedGeneration_.empty() || consumedGeneration != consumedGeneration_ || surface != consumedSurface_)
            return false;
        issued_ = true;
        return true;
    }

    void suspendExecution() {
        ready_ = false;
        consumedGeneration_.clear();
        consumedSurface_.clear();
    }

    bool holdAllowed(double now) const {
        const auto elapsed = now - holdStarted_;
        // Keep a live but stuck service or failed Shell attempt from trapping
        // the player. Expiry releases controls, never the accepted Return intent.
        return pending() && elapsed >= 0 && elapsed < 15 && (!executeOffered_ || consumed());
    }

    static bool permitsAction(const std::string& action) {
        return action == "retry_result_save" || action == "quit_game";
    }

    void clear() {
        nonce_.clear(); activity_.clear(); fixture_.clear(); intent_.clear();
        ready_ = false; issued_ = false; executeOffered_ = false;
        consumedGeneration_.clear(); consumedSurface_.clear();
    }
    bool pending() const { return !activity_.empty(); }
    bool issued() const { return issued_; }
    bool ready() const { return ready_; }
    bool consumed() const { return !consumedGeneration_.empty(); }
    bool arrived() const { return arrived_; }
    bool executeOffered() const { return executeOffered_; }
    bool matchesNonce(const std::string& nonce) const { return !pending() || nonce == nonce_; }

private:
    bool safe(const NativeReturnContext& context) const {
        return context.owned && context.fresh && context.offline && !context.online && !context.replay &&
            context.buildVerified && context.nonce == nonce_ && context.inGame && context.matchAvailable;
    }
    static bool validGeneration(const std::string& value) {
        if (value.empty() || value.size() > 20 || value.front() == '0') return false;
        for (const auto c : value) if (c < '0' || c > '9') return false;
        return value.size() < 20 || value <= "18446744073709551615";
    }
    bool durable(const Json& state) const {
        if (!state.is_object() || stringValue(state, "bridge_session") != nonce_ ||
            !state.contains("protocol") || !state["protocol"].is_number_integer() || state["protocol"] != 1 ||
            !state.contains("offline") || !state["offline"].is_boolean() || !state["offline"].get<bool>()) return false;
        const auto session = objectValue(state, "session");
        const auto ready = objectValue(state, "native_return_ready");
        if (ready.size() != 2 || stringValue(ready, "session_id") != activity_ ||
            !ready.contains("fixture_id") || !ready["fixture_id"].is_string() ||
            ready["fixture_id"].get<std::string>() != fixture_) return false;
        if (!session.contains("id") || !session["id"].is_null() ||
            !session.contains("fixture_id") || !session["fixture_id"].is_null() ||
            stringValue(session, "state") != "Idle" ||
            stringValue(session, "kind") != "hub" ||
            !explicitFalse(session, "worker_running") || !explicitFalse(session, "busy") ||
            !state.contains("error") || !state["error"].is_string() || !state["error"].get<std::string>().empty())
            return false;
        if (!state.contains("career") || (!state["career"].is_null() && !state["career"].is_object())) return false;
        const auto career = objectValue(state, "career");
        if (state["career"].is_object() && (!career.contains("pending_session") || !career["pending_session"].is_null())) return false;
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
    bool arrived_ = false;
    bool executeOffered_ = false;
    double holdStarted_ = 0;
    std::string consumedGeneration_;
    std::string consumedSurface_;
};
}
