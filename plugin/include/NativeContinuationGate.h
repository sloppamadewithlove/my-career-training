#pragma once

#include "NativeReturnGate.h"

namespace mct {

// In-memory continuation only. It cannot navigate or launch anything itself.
// The host supplies fresh owned-game observations, then consumes one payload.
class NativeContinuationGate {
public:
    bool arm(const std::string& nonce, const Json& payload, const std::string& intent) {
        if (nonce.empty() || !NativeReturnGate::validRequest("prepare_next_match", payload, intent)) return false;
        if (nonce == nonce_ && payload == payload_ && intent == intent_) return true;
        if (pending() || (attempted_ && nonce == nonce_ &&
            stringValue(payload, "expected_session_id") == activity_ &&
            stringValue(payload, "expected_fixture_id") == fixture_)) return false;
        clear();
        nonce_ = nonce;
        activity_ = stringValue(payload, "expected_session_id");
        fixture_ = stringValue(payload, "expected_fixture_id");
        nextFixture_ = stringValue(payload, "expected_next_fixture_id");
        intent_ = intent;
        payload_ = payload;
        return true;
    }

    void poll(const NativeReturnContext& context, const Json& state, bool returnPending, bool returnArrived) {
        if (!pending()) {
            if (attempted_) {
                if (!safeScope(context) || (context.fresh && !validState(state))) { clear(); return; }
                const auto session = objectValue(state, "session");
                const auto active = stringValue(session, "id");
                if (context.fresh && !active.empty() && (active != activity_ ||
                    stringValue(session, "fixture_id") != fixture_)) sendFailed_ = false;
            }
            return;
        }
        ready_ = false;
        if (!safeScope(context)) { clear(); return; }
        // A short IPC gap or a movie unload may delay continuation, never start
        // it or erase the accepted request in the same owned game.
        if (!context.fresh) return;
        if (!validState(state)) { clear(); return; }
        const auto session = objectValue(state, "session");
        const auto active = stringValue(session, "id");
        if (!active.empty() && (active != activity_ || stringValue(session, "fixture_id") != fixture_)) {
            clear(); return;
        }
        committed_ = committed_ || nextAcknowledged(state);
        const auto rejection = objectValue(state, "native_next_rejected");
        if (!committed_ && active == activity_ && stringValue(session, "fixture_id") == fixture_ &&
            rejection.size() == 3 && stringValue(rejection, "session_id") == activity_ &&
            stringValue(rejection, "fixture_id") == fixture_ && stringValue(rejection, "intent") == intent_) {
            clear();
            rejected_ = true;
            return;
        }
        if (returnPending) sawReturnPending_ = true;
        ready_ = durable(state);
        if (ready_ && sawReturnPending_ && !returnPending && returnArrived && atFreshRoot(context))
            arrived_ = true;
    }

    Json takeStart(const NativeReturnContext& context, const Json& state, bool returnArrived) {
        if (!pending() || !arrived_ || !sawReturnPending_ || !returnArrived || !safeScope(context) ||
            !context.fresh || !atFreshRoot(context) || !durable(state)) return Json::object();
        attempted_ = true;
        ready_ = false;
        return {{"expected_session_id", activity_}, {"expected_fixture_id", fixture_},
            {"expected_next_fixture_id", nextFixture_}, {"continuation_intent", intent_}};
    }

    void noteSendResult(bool sent) {
        if (!attempted_ || sendOutcomeKnown_) return;
        sendOutcomeKnown_ = true;
        sendFailed_ = !sent;
    }
    Json presentationState(const Json& state) const {
        auto display = state;
        if (sendFailed_ && validState(state))
            display["error"] = "Next match could not be confirmed. Choose Quit My Career and reopen it; your finished result is saved.";
        return display;
    }

    void clear() {
        nonce_.clear(); activity_.clear(); fixture_.clear(); nextFixture_.clear(); intent_.clear();
        payload_ = Json::object();
        ready_ = committed_ = arrived_ = sawReturnPending_ = attempted_ = rejected_ = false;
        sendFailed_ = sendOutcomeKnown_ = false;
    }
    bool pending() const { return !activity_.empty() && !attempted_; }
    bool ready() const { return ready_; }
    bool attempted() const { return attempted_; }
    bool rejected() const { return rejected_; }
    bool matchesNonce(const std::string& nonce) const { return !nonce_.empty() && nonce == nonce_; }

private:
    bool safeScope(const NativeReturnContext& c) const {
        return c.owned && c.offline && !c.online && !c.replay && c.buildVerified && c.nonce == nonce_;
    }
    static bool atFreshRoot(const NativeReturnContext& c) {
        return !c.inGame && c.frontendRoot && c.frontendReady;
    }
    bool validState(const Json& state) const {
        return state.is_object() && stringValue(state, "bridge_session") == nonce_ &&
            state.contains("protocol") && state["protocol"].is_number_integer() && state["protocol"] == 1 &&
            state.contains("offline") && state["offline"].is_boolean() && state["offline"].get<bool>();
    }
    bool nextAcknowledged(const Json& state) const {
        const auto ack = objectValue(state, "native_next_ready");
        return ack.size() == 4 && stringValue(ack, "session_id") == activity_ &&
            stringValue(ack, "fixture_id") == fixture_ && stringValue(ack, "next_fixture_id") == nextFixture_ &&
            stringValue(ack, "intent") == intent_;
    }
    static bool falseField(const Json& object, const char* name) {
        return object.contains(name) && object[name].is_boolean() && !object[name].get<bool>();
    }
    bool durable(const Json& state) const {
        if (!validState(state) || !nextAcknowledged(state)) return false;
        const auto ack = objectValue(state, "native_return_ready");
        const auto session = objectValue(state, "session");
        const auto career = objectValue(state, "career");
        const auto result = objectValue(state, "latest_result");
        const auto provenance = stringValue(result, "provenance");
        return ack.size() == 2 && stringValue(ack, "session_id") == activity_ &&
            stringValue(ack, "fixture_id") == fixture_ &&
            session.contains("id") && session["id"].is_null() &&
            session.contains("fixture_id") && session["fixture_id"].is_null() &&
            stringValue(session, "state") == "Idle" && stringValue(session, "kind") == "hub" &&
            falseField(session, "worker_running") && falseField(session, "busy") &&
            career.contains("pending_session") && career["pending_session"].is_null() &&
            state.contains("error") && state["error"].is_string() && state["error"].get<std::string>().empty() &&
            stringValue(result, "session_id") == activity_ && stringValue(result, "fixture_id") == fixture_ &&
            (provenance == "game" || provenance == "forfeit");
    }

    std::string nonce_, activity_, fixture_, nextFixture_, intent_;
    Json payload_ = Json::object();
    bool ready_ = false;
    bool committed_ = false;
    bool arrived_ = false;
    bool sawReturnPending_ = false;
    bool attempted_ = false;
    bool rejected_ = false;
    bool sendFailed_ = false;
    bool sendOutcomeKnown_ = false;
};
}
