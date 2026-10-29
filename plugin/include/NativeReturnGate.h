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
    static bool validRequest(const std::string& action, const Json& payload, const std::string& intent) {
        if (!payload.is_object() ||
            !payload.contains("expected_session_id") || !payload["expected_session_id"].is_string() ||
            !payload.contains("expected_fixture_id") || !payload["expected_fixture_id"].is_string()) return false;
        const auto activity = payload["expected_session_id"].get<std::string>();
        const auto fixture = payload["expected_fixture_id"].get<std::string>();
        if (activity.empty() || activity.size() > 128 || fixture.size() > 128 || !validIntent(intent)) return false;
        if (action == "return_hub")
            return payload.size() == 3 && payload.contains("abandon") && payload["abandon"].is_boolean();
        if (action == "prepare_next_match") return validPrepare(payload, fixture, intent);
        return action == "forfeit_match" && !fixture.empty() && payload.size() == 4 &&
            payload.contains("confirm") && payload["confirm"].is_boolean() && payload["confirm"].get<bool>() &&
            stringValue(payload, "return_intent") == intent;
    }

    bool arm(const std::string& nonce, const Json& payload, const std::string& intent, double now = 0,
             const std::string& action = "return_hub") {
        if (nonce.empty() || !validRequest(action, payload, intent)) return false;
        const auto activity = payload["expected_session_id"].get<std::string>();
        const auto fixture = payload["expected_fixture_id"].get<std::string>();
        // Repeated clicks cannot re-arm an already issued return for this activity.
        // Prepare may repeat only the same intent, target and lineup, and that
        // repeat must not reset arrival, consumption, or an offered exit.
        if (action == "prepare_next_match") {
            const auto next = payload["expected_next_fixture_id"].get<std::string>();
            if (pending() && nonce == nonce_ && activity == activity_ && fixture == fixture_) {
                if (action_ == "prepare_next_match" && intent_ == intent && nextFixture_ == next && payload_ == payload)
                    return true;
                return false;
            }
            if (pending()) return false;
        } else {
            if (nonce == nonce_ && activity == activity_ && fixture == fixture_) return action == action_;
            if (pending()) return false;
        }
        nonce_ = nonce;
        activity_ = activity;
        fixture_ = fixture;
        intent_ = intent;
        action_ = action;
        if (action == "prepare_next_match") {
            nextFixture_ = payload["expected_next_fixture_id"].get<std::string>();
            payload_ = payload;
        } else {
            nextFixture_.clear();
            payload_ = Json::object();
        }
        ready_ = false;
        nextCommitted_ = false;
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
        // Exact precommit continuation rejection only. A matching next-ready
        // acknowledgement is commit proof. Generic errors are not.
        if (action_ == "prepare_next_match") nextCommitted_ = nextCommitted_ || nextReady(state);
        if (action_ == "prepare_next_match" && !executeOffered_ && !issued_ && !nextCommitted_ &&
            activeId == activity_ && stringValue(session, "fixture_id") == fixture_ && nextRejected(state)) {
            clear();
            return false;
        }
        // A failed atomic save may restore ordinary pause controls, but only
        // this exact host-generated request's explicit rejection can do so.
        // Generic errors and stale pre-dispatch snapshots cannot cancel intent.
        const auto rejected = objectValue(state, "native_forfeit_rejected");
        if (action_ == "forfeit_match" && !executeOffered_ && !issued_ && !forfeitCommitted(state) &&
            activeId == activity_ && stringValue(session, "fixture_id") == fixture_ &&
            rejected.size() == 3 && stringValue(rejected, "session_id") == activity_ &&
            stringValue(rejected, "fixture_id") == fixture_ && stringValue(rejected, "intent") == intent_) {
            clear(); return false;
        }
        ready_ = durable(state);
        if (!ready_) { suspendExecution(); return false; }
        // A title screen and map transition are both outside the match. Only a
        // current authored hub handshake plus the stock root stack completes it.
        if (!context.inGame) {
            if (context.frontendReady && context.frontendRoot) {
                nonce_.clear(); activity_.clear(); fixture_.clear(); intent_.clear(); action_.clear();
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
        nonce_.clear(); activity_.clear(); fixture_.clear(); intent_.clear(); action_.clear();
        nextFixture_.clear(); payload_ = Json::object();
        ready_ = false; issued_ = false; executeOffered_ = false; nextCommitted_ = false;
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
    bool forfeitCommitted(const Json& state) const {
        const auto result = objectValue(state, "latest_result");
        const auto home = stringValue(result, "home");
        const auto away = stringValue(result, "away");
        const auto winner = stringValue(result, "winner");
        return stringValue(result, "session_id") == activity_ && stringValue(result, "fixture_id") == fixture_ &&
            stringValue(result, "provenance") == "forfeit" && stringValue(result, "outcome") == "forfeited" &&
            explicitFalse(result, "simulated") &&
            stringValue(result, "forfeited_by") == "human" && !winner.empty() && winner != "human" &&
            ((home == "human" && away == winner) || (away == "human" && home == winner));
    }
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
        if (state["career"].is_object()) {
            if (!career.contains("pending_session")) return false;
            const auto& pending = career["pending_session"];
            if (!pending.is_null()) {
                const auto pendingSession = stringValue(pending, "session_id");
                const auto pendingFixture = stringValue(pending, "fixture_id");
                const bool preserveForNonCareerReturn = action_ == "return_hub" && fixture_.empty() &&
                    pending.is_object() && pendingSession != activity_ && !pendingSession.empty() && pendingSession.size() <= 128 &&
                    !pendingFixture.empty() && pendingFixture.size() <= 128;
                if (!preserveForNonCareerReturn) return false;
            }
        }
        if (action_ == "prepare_next_match" && (!state["career"].is_object() ||
            !nextReady(state) || !prepareResult(state))) return false;
        if (action_ == "forfeit_match" && !forfeitCommitted(state)) return false;
        return true;
    }
    static bool validPrepare(const Json& payload, const std::string& fixture, const std::string& intent) {
        if (fixture.empty() || payload.size() != 5 || !payload.contains("expected_next_fixture_id") ||
            !payload["expected_next_fixture_id"].is_string() || !payload.contains("lineup_ids") ||
            !payload["lineup_ids"].is_array() || !payload.contains("continuation_intent") ||
            !payload["continuation_intent"].is_string() ||
            payload["continuation_intent"].get<std::string>() != intent) return false;
        const auto next = payload["expected_next_fixture_id"].get<std::string>();
        if (next.empty() || next.size() > 128 || next == fixture) return false;
        const auto& lineup = payload["lineup_ids"];
        if (lineup.size() > 3) return false;
        for (std::size_t i = 0; i < lineup.size(); ++i) {
            const auto& id = lineup[i];
            if (!id.is_string()) return false;
            const auto text = id.get<std::string>();
            if (text.empty() || text.size() > 128) return false;
            for (std::size_t j = 0; j < i; ++j) if (lineup[j] == id) return false;
        }
        return true;
    }
    bool nextReady(const Json& state) const {
        const auto ready = objectValue(state, "native_next_ready");
        return ready.size() == 4 && stringValue(ready, "session_id") == activity_ &&
            stringValue(ready, "fixture_id") == fixture_ &&
            stringValue(ready, "next_fixture_id") == nextFixture_ &&
            stringValue(ready, "intent") == intent_;
    }
    bool nextRejected(const Json& state) const {
        const auto rejected = objectValue(state, "native_next_rejected");
        return rejected.size() == 3 && stringValue(rejected, "session_id") == activity_ &&
            stringValue(rejected, "fixture_id") == fixture_ && stringValue(rejected, "intent") == intent_;
    }
    bool prepareResult(const Json& state) const {
        const auto result = objectValue(state, "latest_result");
        const auto provenance = stringValue(result, "provenance");
        return stringValue(result, "session_id") == activity_ && stringValue(result, "fixture_id") == fixture_ &&
            (provenance == "game" || provenance == "forfeit");
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
    std::string action_;
    std::string nextFixture_;
    Json payload_ = Json::object();
    bool ready_ = false;
    bool nextCommitted_ = false;
    bool issued_ = false;
    bool arrived_ = false;
    bool executeOffered_ = false;
    double holdStarted_ = 0;
    std::string consumedGeneration_;
    std::string consumedSurface_;
};
}
